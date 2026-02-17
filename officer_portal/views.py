from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, FileResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
import json
import logging
import os
import random
import io

from .models import OfficerProfile, Case, Evidence, AuditLog, ChatMessage
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View, TemplateView

# AI Service Integration
from . import ai_service
from .ai_engine import TrinetraAI  # Ensure this is imported

# PDF Generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

logger = logging.getLogger(__name__)

# ==============================================================================
# UTILITY
# ==============================================================================
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# ==============================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def officer_login(request):
    """
    Custom login view for officers.
    """
    if request.user.is_authenticated:
        return redirect('officer_dashboard')
        
    if request.method == 'POST':
        identifier = request.POST.get('identifier') # Badge or Username
        password = request.POST.get('password')
        
        user = authenticate(request, username=identifier, password=password)
        
        if user is not None:
            if user.is_staff: # Ensure officer level
                login(request, user)
                AuditLog.objects.create(
                    user=user,
                    action="LOGIN",
                    ip_address=get_client_ip(request),
                    details="Officer Login Successful"
                )
                return redirect('officer_dashboard')
            else:
                messages.error(request, "Access Denied: Officer Clearance Required.")
        else:
            messages.error(request, "Invalid Credentials.")
            
    return render(request, 'officer_portal/login.html')

class AdminLoginOverrideView(LoginView):
    template_name = 'admin/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        user = self.request.user
        if user.is_superuser:
            return reverse_lazy('admin_2fa')
        return reverse_lazy('admin:index')

class Admin2FAView(LoginRequiredMixin, TemplateView):
    template_name = 'admin/2fa.html'

    def post(self, request, *args, **kwargs):
        code = request.POST.get('code')
        # Hardcoded for demo/dev; replace with TOTP in prod
        if code == "123456":
            request.session['admin_2fa_verified'] = True
            return redirect('admin:index')
        else:
            messages.error(request, "Invalid 2FA Code")
            return redirect('admin_2fa')

def custom_admin_logout(request):
    """
    Custom logout that clears session and redirects to admin login.
    """
    logout(request)
    return redirect('/admin/login/?next=/admin/')

# ==============================================================================
# DASHBOARD VIEWS
# ==============================================================================

@login_required
def officer_dashboard(request):
    """
    Main specific dashboard for logged-in officers.
    """
    # 1. Fetch relevant data
    recent_cases = Case.objects.filter(assigned_officer=request.user).order_by('-created_at')[:5]
    recent_evidence = Evidence.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')[:5]
    
    # 2. Render Template
    context = {
        'recent_cases': recent_cases,
        'recent_evidence': recent_evidence,
        'section': 'dashboard'
    }
    return render(request, 'officer_portal/dashboard.html', context)

@login_required
@require_POST
def ai_chat_endpoint(request):
    """
    API Endpoint for the Officer Dashboard AI Chat.
    """
    try:
        user_message = ""
        attachment = None
        case_id = None  # Initialize
        
        # 1. Parse Request Data (JSON vs Form)
        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            case_id = data.get('case_id')
        else:
            # Form Data
            user_message = request.POST.get('message', '')
            case_id = request.POST.get('case_id')
            if 'attachment' in request.FILES:
                attachment = request.FILES['attachment']
        
        if not user_message and not attachment:
            return JsonResponse({'response': "Empty transmission received."}, status=400)

        # 2. Prepare Context
        user_context = {
            'username': request.user.username,
            'is_staff': request.user.is_staff,
            'id': request.user.id
        }
        
        # 3. CALL THE ENGINE (The "Brain")
        # [CRITICAL FIX] Use TrinetraAI.process_query instead of calling ai_service directly.
        # This ensures the case is created in NeonDB before we try to analyze logs.
        ai_reply = TrinetraAI.process_query(user_message, user_context, attachment, case_id=case_id)
        
        # 4. Persistence (Save to Local Django DB)
        # Resolve Case Object if possible
        case_obj = None
        if case_id:
            case_obj = Case.objects.filter(case_no=case_id).first()

        ChatMessage.objects.create(
            user=request.user,
            query=user_message,
            response=ai_reply,
            file_attachment=attachment,
            case=case_obj
        )
        
        return JsonResponse({'response': ai_reply})

    except json.JSONDecodeError:
        return JsonResponse({'response': "Invalid Protocol. JSON required."}, status=400)
    except Exception as e:
        logger.error(f"Chat Endpoint Error: {e}")
        return JsonResponse({'response': f"System Error: {str(e)}"}, status=500)

@login_required
def authorize_ai(request):
    """
    Endpoint for the 'Unlock AI' button/modal.
    """
    if request.method == "POST":
        # Log the authorization
        AuditLog.objects.create(
            user=request.user,
            action="AI_AUTH",
            ip_address=get_client_ip(request),
            details="Authorized AI usage for session"
        )
        return JsonResponse({"status": "authorized"})
    return JsonResponse({"status": "failed"}, status=403)

@login_required
def generate_legal(request, case_id):
    """
    Endpoint to trigger PDF generation based on AI analysis.
    """
    try:
        # 1. Verify Case Ownership/Access
        case = get_object_or_404(Case, case_no=case_id)
        
        # 2. Call AI to draft content
        # For now, we simulate or gather existing facts.
        # Ideally, we pass the case summary or logs to the AI.
        facts_summary = f"Case {case.case_no}: {case.title}. {case.description}"
        
        # Use AI Service to get JSON
        legal_json = ai_service.generate_legal_doc(case_id, facts_summary)
        
        # Check for error
        if "error" in legal_json:
            return JsonResponse({"error": legal_json["error"]}, status=500)
            
        return JsonResponse({
            "status": "ready",
            "download_url": f"/portal/case/{case_id}/download_pdf/",
            "preview_data": legal_json 
        })
        
    except Exception as e:
        logger.error(f"Legal Gen Error: {e}")
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def ai_lab(request):
    """
    Dedicated AI Lab View.
    """
    # Fetch recent chat history for this user
    chat_history = ChatMessage.objects.filter(user=request.user).order_by('-timestamp')[:50]
    
    context = {
        'chat_history': chat_history,
        'section': 'ai_lab'
    }
    return render(request, 'officer_portal/ai_lab.html', context)

@login_required
def create_case_endpoint(request):
    """
    Endpoint to create a new case manually.
    """
    if request.method == "POST":
        title = request.POST.get('title')
        case_no = request.POST.get('case_no')
        description = request.POST.get('description')
        
        if Case.objects.filter(case_no=case_no).exists():
             return JsonResponse({"status": "error", "message": "Case ID already exists."})
             
        Case.objects.create(
            title=title,
            case_no=case_no,
            description=description,
            assigned_officer=request.user,
            status='OPEN'
        )
        return JsonResponse({"status": "success"})
        
    return JsonResponse({"status": "error", "message": "Invalid method"})

@login_required
def download_case_pdf(request, case_id):
    """
    Generates and returns a PDF file for the given case.
    """
    # 1. Get Data (Mocked or from DB/AI)
    # in real flow, we might cache the JSON result from 'generate_legal'
    case = get_object_or_404(Case, case_no=case_id)
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 750, "TRINETRA: LEGAL INTELLIGENCE REPORT")
    
    p.setFont("Helvetica", 12)
    p.drawString(50, 720, f"Case ID: {case.case_no}")
    p.drawString(50, 700, f"Title: {case.title}")
    p.drawString(50, 680, f"Date: {timezone.now().strftime('%Y-%m-%d')}")
    
    p.line(50, 670, 550, 670)
    
    # Body
    text = p.beginText(50, 650)
    text.setFont("Helvetica", 10)
    
    # This is a placeholder. In production, we'd use the AI JSON.
    lines = [
        "SUMMARY OF FACTS:",
        case.description[:500],
        "",
        "LEGAL ANALYSIS:",
        "Based on the provided logs and evidence, Trinetra AI has detected...",
        "(AI Generated Analysis would go here)",
        "",
        "RECOMMENDATION:",
        "Proceed with formal investigation."
    ]
    
    for line in lines:
        text.textLine(line)
        
    p.drawText(text)
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"Trinetra_Report_{case_id}.pdf")
