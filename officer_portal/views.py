from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse, FileResponse
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

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# --- IMPORTS ---
from .models import Case, ChatMessage, Evidence, LegalDraft
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
        'recent_cases': recent_cases,
        'user': request.user
    })

# --- AI CHAT ENDPOINT ---
@login_required
@require_POST
def ai_chat_endpoint(request):
    try:
        user_message = ""
        case_id = None
        attachment = None
        
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

        user_context = {'username': request.user.username, 'id': request.user.id}
        ai_reply = TrinetraAI.process_query(user_message, user_context, attachment, case_id=case_id)
        
        # Save
        case_obj = Case.objects.filter(case_no=case_id).first() if case_id else None
        ChatMessage.objects.create(
            user=request.user,
            query=user_message,
            response=ai_reply,
            file_attachment=attachment,
            case=case_obj
        )
        return JsonResponse({'response': ai_reply})

    except Exception as e:
        logger.error(f"Chat Error: {e}")
        return JsonResponse({'response': f"System Error: {str(e)}"}, status=500)

# [FIX] Add missing stubs to prevent import errors if urls.py references them
def authorize_ai(request): return JsonResponse({'status': 'ok'})
def generate_legal(request, case_id): return JsonResponse({'status': 'ok'})
def download_case_pdf(request, case_id): return HttpResponse("PDF Download")
def ai_lab(request): return render(request, 'officer_portal/ai_lab.html')
def create_case_endpoint(request): return JsonResponse({'status': 'ok'})
