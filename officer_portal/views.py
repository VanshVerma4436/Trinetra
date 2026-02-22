from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse, FileResponse, HttpResponseBadRequest, HttpResponseServerError, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
# [CRITICAL FIX] This import was missing or shadowed on your server
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.conf import settings
import json
import logging
import io
import uuid
import threading

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# --- IMPORTS ---
from .models import Case, ChatMessage, Evidence, LegalDraft, AIUsageLog
try:
    from authentication.models import OfficerProfile
except ImportError:
    pass
try:
    from audit_logs.models import AuditLog
except ImportError:
    from audit_logs.models import ImmutableLog as AuditLog

from .ai_engine import TrinetraAI

logger = logging.getLogger(__name__)

# --- UTILS ---
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

# --- VIEWS ---

def officer_login(request):
    if request.user.is_authenticated:
        return redirect('officer_dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username') or request.POST.get('identifier')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect('officer_dashboard')
            else:
                messages.error(request, "Access Denied: Officer Clearance Required.")
        else:
            messages.error(request, "Invalid Credentials.")
            
    return render(request, 'officer_portal/login.html')

# [FIX] Admin Login Override
class AdminLoginOverrideView(LoginView):
    template_name = 'admin/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        user = self.request.user
        if user.is_superuser:
            return '/portal/admin-security/2fa/' # Explicit URL
        return '/admin/'

# [FIX] 2FA View with Template Check
class Admin2FAView(LoginRequiredMixin, TemplateView):
    template_name = 'admin/2fa.html' # Must match filename case EXACTLY

    def post(self, request, *args, **kwargs):
        code = request.POST.get('code')
        # Bypass for dev/testing
        if code == "123456" or settings.DEBUG:
            request.session['admin_2fa_verified'] = True
            return redirect('/admin/')
        else:
            messages.error(request, "Invalid 2FA Code")
            return redirect('admin_2fa')

def custom_admin_logout(request):
    logout(request)
    return redirect('/admin/login/')

@login_required
def officer_dashboard(request):
    recent_cases = Case.objects.filter(assigned_officer=request.user).order_by('-created_at')[:5]
    return render(request, 'officer_portal/dashboard.html', {
        'cases': recent_cases,
        'user': request.user
    })

# --- BACKGROUND TASK STORE (in-memory, per-process) ---
# Stores results from AI calls so browsers can poll for them.
_ai_task_store = {}

# --- AI CHAT ENDPOINT (NON-BLOCKING) ---
@login_required
@require_POST
def ai_chat_endpoint(request):
    """
    Immediately returns a task_id. The AI call runs in a background thread.
    The browser polls /api/chat/status/<task_id>/ until the result is ready.
    This avoids Azure's ~230-second proxy connection timeout.
    """
    try:
        user_message = ""
        case_id = None
        attachment = None
        temp_path = None

        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            case_id = data.get('case_id')
        else:
            user_message = request.POST.get('message', '')
            case_id = request.POST.get('case_id')
            if 'attachment' in request.FILES:
                attachment = request.FILES['attachment']

        if not user_message and not attachment:
            return JsonResponse({'response': "Empty transmission."}, status=400)

        # Save uploaded file to a temp path so the background thread can read it
        if attachment:
            import tempfile, os
            suffix = os.path.splitext(attachment.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in attachment.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name

        task_id = str(uuid.uuid4())
        _ai_task_store[task_id] = {'status': 'pending', 'response': None}

        user_id = request.user.id
        username = request.user.username

        def run_ai():
            try:
                from django import db
                db.close_old_connections()  # Fresh DB connection in thread
                from .ai_service import analyze_logs
                ai_reply = analyze_logs(case_id or f"CMD-USER-{user_id}", user_message, temp_path)

                # Save to DB from the background thread
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user_obj = User.objects.get(pk=user_id)
                case_obj = Case.objects.filter(case_no=case_id).first() if case_id else None
                ChatMessage.objects.create(
                    user=user_obj,
                    query=user_message,
                    response=ai_reply,
                    case=case_obj
                )
                _ai_task_store[task_id] = {'status': 'done', 'response': ai_reply}
            except Exception as e:
                logger.error(f"Background AI Error: {e}")
                _ai_task_store[task_id] = {'status': 'done', 'response': f"System Error: {str(e)}"}
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                db.close_old_connections()

        thread = threading.Thread(target=run_ai, daemon=True)
        thread.start()

        return JsonResponse({'task_id': task_id, 'status': 'pending'})

    except Exception as e:
        logger.error(f"Chat Dispatch Error: {e}")
        return JsonResponse({'response': f"System Error: {str(e)}"}, status=500)


# --- AI TASK STATUS POLL ---
@login_required
def ai_task_status(request, task_id):
    """Browser polls this every 3s to check if the AI has finished."""
    task = _ai_task_store.get(task_id)
    if not task:
        return JsonResponse({'status': 'not_found'}, status=404)
    if task['status'] == 'done':
        # Clean up memory after delivering the result
        _ai_task_store.pop(task_id, None)
        return JsonResponse({'status': 'done', 'response': task['response']})
    return JsonResponse({'status': 'pending'})

@login_required
@require_POST
def authorize_ai(request):
    """
    Handles the security protocol modal to log AI usage before entering the WORMHOLE.
    """
    complaint_no = request.POST.get('complaint_no')
    justification = request.POST.get('justification')
    
    if complaint_no and justification:
        AIUsageLog.objects.create(
            user=request.user,
            complaint_no=complaint_no,
            justification=justification
        )
        # Redirect to the AI Lab with the case ID to load history
        return redirect(f"{reverse('ai_lab')}?case_id={complaint_no}")
    
    return HttpResponseBadRequest("Missing required compliance fields.")

@login_required
def generate_legal(request):
    """
    Generates a PDF legal document using the Trinetra AI and returns it to the user.
    """
    case_id = request.GET.get('case_id')
    if not case_id:
        return HttpResponseBadRequest("Missing case ID.")
        
    case = get_object_or_404(Case, case_no=case_id)
    
    # 1. Ask AI to draft the document based on case details
    instruction = f"Draft an official legal summary for case {case.case_no}. Suspect: {case.suspect_name}. Details: {case.description}"
    ai_response = TrinetraAI.generate_legal_doc(case.case_no, instruction)
    
    if isinstance(ai_response, dict) and "error" in ai_response:
        return HttpResponseServerError(f"AI Generation Failed: {ai_response['error']}")
        
    # Example AI response JSON structure we expect: 
    # {'title': '...', 'facts': '...', 'legal_analysis': '...', 'conclusion': '...'}
    
    title = ai_response.get('title', f"Legal Report - {case.case_no}")
    facts = ai_response.get('facts', case.description)
    law = ai_response.get('legal_analysis', 'Awaiting full AI analysis.')
    conclusion = ai_response.get('conclusion', 'Investigation ongoing.')
    
    # Save the draft history 
    draft = LegalDraft.objects.create(
        user=request.user,
        reference_no=case.case_no,
        justification="System Generated via WORMHOLE PDF request",
        generated_content=f"TITLE: {title}\nFACTS: {facts}\nLAW: {law}\nCONCLUSION: {conclusion}"
    )
    
    # 2. Convert to PDF
    import io
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from datetime import datetime
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 750, "TRINETRA SECURE PORTAL - OFFICIAL LEGAL DRAFT")
    p.setFont("Helvetica", 10)
    p.drawString(50, 735, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Officer: {request.user.username}")
    p.line(50, 725, 550, 725)
    
    # Content
    y = 700
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, f"Ref No: {draft.reference_no}")
    y -= 20
    p.drawString(50, y, f"Subject: {title}")
    y -= 30
    
    p.setFont("Helvetica-Oblique", 11)
    p.drawString(50, y, "1. Statement of Facts:")
    y -= 15
    p.setFont("Helvetica", 10)
    
    # Simple word wrap logic for PDF
    import textwrap
    for line in textwrap.wrap(facts, 90):
        p.drawString(50, y, line)
        y -= 15
        if y < 50:
            p.showPage()
            y = 750
            p.setFont("Helvetica", 10)
    
    y -= 15
    p.setFont("Helvetica-Oblique", 11)
    p.drawString(50, y, "2. Legal Analysis:")
    y -= 15
    p.setFont("Helvetica", 10)
    for line in textwrap.wrap(law, 90):
        p.drawString(50, y, line)
        y -= 15
        if y < 50:
            p.showPage()
            y = 750
            p.setFont("Helvetica", 10)
            
    y -= 15
    p.setFont("Helvetica-Oblique", 11)
    p.drawString(50, y, "3. Conclusion:")
    y -= 15
    p.setFont("Helvetica", 10)
    for line in textwrap.wrap(conclusion, 90):
        p.drawString(50, y, line)
        y -= 15
        if y < 50:
            p.showPage()
            y = 750
            p.setFont("Helvetica", 10)
            
    p.showPage()
    p.save()
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Legal_Opinion_{case.case_no}.pdf"'
    return response

@login_required
def ai_lab(request):
    case_id = request.GET.get('case_id', '')
    context = {
        'case_id': case_id
    }
    return render(request, 'officer_portal/ai_lab.html', context)
@login_required
@require_POST
def create_case_endpoint(request):
    try:
        data = json.loads(request.body)
        suspect_name = data.get('suspect_name', 'Unknown')
        description = data.get('description', '')
        priority = data.get('priority', 'MEDIUM')
        
        from django.utils.crypto import get_random_string
        case_no = f"TRN-{get_random_string(6).upper()}"
        
        case = Case.objects.create(
            case_no=case_no,
            suspect_name=suspect_name,
            description=description,
            priority=priority,
            assigned_officer=request.user,
            status='OPEN'
        )
        return JsonResponse({'status': 'ok', 'case_no': case.case_no})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def officer_logout(request):
    logout(request)
    return redirect('portal_login')
from django.http import HttpResponse
def factory_reset(request):
    """Temporary endpoint to wipe the DB and recreate admin from Azure."""
    if request.GET.get('key') != 'RESET123':
        return HttpResponse("Unauthorized", status=403)
        
    try:
        from officer_portal.models import Case, ChatMessage, Evidence, LegalDraft, AIUsageLog
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # 1. Delete App Data
        Evidence.objects.all().delete()
        ChatMessage.objects.all().delete()
        LegalDraft.objects.all().delete()
        AIUsageLog.objects.all().delete()
        Case.objects.all().delete()
        
        # 2. Delete Non-Admin Users
        User.objects.exclude(username='admin').delete()
        
        # 3. Create Admin
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            msg = "DB wiped and Admin created successfully (admin / admin123)."
        else:
            admin_user = User.objects.get(username='admin')
            admin_user.set_password('admin123')
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.save()
            msg = "DB wiped and existing Admin password reset to admin123."
            
        return HttpResponse(f"<h1>Success!</h1><p>{msg}</p><p><b>Security Warning:</b> Please ask the AI to remove this endpoint now!</p>")
        
    except Exception as e:
        return HttpResponse(f"<h1>Error</h1><p>{str(e)}</p>", status=500)
