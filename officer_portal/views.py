from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views import View
from django.http import JsonResponse, HttpResponse, FileResponse
from io import BytesIO
import json
import logging

logger = logging.getLogger(__name__)
from .utils import verify_client_certificate, log_officer_action
from .ai_engine import TrinetraAI
from .models import ChatMessage, LegalDraft, Case
from .pdf_utils import generate_professional_pdf
from django.http import FileResponse
import io
from datetime import datetime

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@never_cache
def officer_login(request):
    client_ip = get_client_ip(request)
    
    # Certificate Check
    is_cert_valid, cert_msg = verify_client_certificate(request)
    
    if not is_cert_valid:
        log_officer_action(request.user, "BREACH", client_ip, {"reason": f"Cert Failure: {cert_msg}"})
        return render(request, 'officer_portal/access_denied.html', {"reason": "Hardware Security Key Missing"}, status=403)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                log_officer_action(user, "LOGIN", client_ip, {"method": "Password+Cert"})
                return redirect('officer_dashboard')
            else:
                log_officer_action(None, "FAIL", client_ip, {"username": username, "reason": "Inactive Account"})
        else:
             log_officer_action(None, "FAIL", client_ip, {"username": username, "reason": "Bad Credentials"})
             
    return render(request, 'officer_portal/login.html')

class AdminLoginOverrideView(LoginView):
    template_name = 'admin/login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_header'] = "Trinetra Commander"
        context['site_title'] = "Commander Access"
        context['has_permission'] = False 
        context['is_nav_sidebar_enabled'] = False
        return context

    def form_valid(self, form):
        # 1. Log the user in (Standard Django Login)
        response = super().form_valid(form)
        
        # 2. Check if Superuser
        if self.request.user.is_superuser:
            # 3. INTERCEPT: Set 2FA Pending
            self.request.session['admin_2fa_verified'] = False
            # Redirect to 2FA page
            return redirect('admin_2fa')
            
        return response

    def form_invalid(self, form):
        print(f"!!! LOGIN FAILED !!! Errors: {form.errors}")
        print(f"!!! POST Data: {self.request.POST}")
        return super().form_invalid(form)

from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

@method_decorator(never_cache, name='dispatch')
class Admin2FAView(View):
    template_name = 'admin/2fa_verify.html'
    
    def get(self, request):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return redirect('admin_login')
            
        # Generate OTP (Mock)
        import random
        otp = str(random.randint(100000, 999999))
        request.session['server_otp'] = otp
        
        # LOG OTP TO CONSOLE (Simulation)
        import sys
        print("\n" + "="*50)
        print(f" [TRINETRA SECURITY] ADMIN OTP: {otp}")
        print("="*50 + "\n")
        sys.stdout.flush()
        
        return render(request, self.template_name)
        
    def post(self, request):
        user_otp = request.POST.get('otp')
        server_otp = request.session.get('server_otp')
        bio_data = request.POST.get('biometric_data')
        
        # DEV BYPASS: Allow '000000' or correct OTP
        # Fixed Logic: OTP *OR* Biometric (not AND)
        if (user_otp and (user_otp == server_otp or user_otp == "000000")) or bio_data:
            # VERIFIED
            request.session['admin_2fa_verified'] = True
            logger.info(f"Admin 2FA Passed for {request.user.username}")
            return redirect('/admin/')
        else:
            return render(request, self.template_name, {'error': 'Invalid Credentials'})

def custom_admin_logout(request):
    """
    Explicitly clears session and redirects to custom login.
    Avoids default admin logout page which might trigger security scripts.
    """
    from django.contrib.auth import logout
    logout(request)
    request.session.flush()
    return redirect('admin_login')

@never_cache
@login_required(login_url='portal_login')
def officer_dashboard(request):
    client_ip = get_client_ip(request)
    
    # Iron Dome Check
    is_cert_valid, _ = verify_client_certificate(request)
    if not is_cert_valid:
        return redirect('portal_login')
        
    # Fetch Active Cases for this Officer
    active_cases = Case.objects.filter(officer=request.user, status='OPEN').order_by('-created_at')
    
    # Calculate Stats
    case_count = active_cases.count()
    
    # Determine Threat Level
    threat_level = "LOW"
    threat_class = "t-low"
    
    if active_cases.filter(priority='HIGH').exists():
        threat_level = "CRITICAL"
        threat_class = "t-high"
    elif active_cases.filter(priority='MEDIUM').exists():
        threat_level = "ELEVATED"
        threat_class = "t-med"
        
    # Fetch History (Legal Drafts)
    recent_drafts = LegalDraft.objects.filter(user=request.user).order_by('-timestamp')[:5]

    return render(request, 'officer_portal/dashboard.html', {
        'user': request.user,
        'ip': client_ip,
        'cases': active_cases,
        'recent_cases': recent_drafts,
        'case_count': case_count,
        'threat_level': threat_level,
        'threat_class': threat_class
    })

@login_required
@require_POST
def ai_chat_endpoint(request):
    """
    API Endpoint for the Officer Dashboard AI Chat.
    """
    try:
        # Handle standard JSON or Multipart Form
        user_message = ""
        attachment = None
        
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            user_message = data.get('message', '')
        else:
            # Form Data with Files
            user_message = request.POST.get('message', '')
            if 'attachment' in request.FILES:
                attachment = request.FILES['attachment']
        
        if not user_message and not attachment:
            return JsonResponse({'response': "Empty transmission received."}, status=400)

        # Context for the AI
        user_context = {
            'username': request.user.username,
            'is_staff': request.user.is_staff
        }
        
        # EXTRACT CASE ID
        case_id = request.POST.get('case_id')
        if not case_id and request.content_type == 'application/json':
             data = json.loads(request.body)
             case_id = data.get('case_id')

        # Process via Engine
        ai_reply = TrinetraAI.process_query(user_message, user_context, attachment, case_id)
        
        # Resolve Case Object for Persistence
        case_obj = None
        if case_id:
            case_obj = Case.objects.filter(case_no=case_id).first()

        # PERSISTENCE SAVE
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
        return JsonResponse({'response': f"System Error: {str(e)}"}, status=500)

from .models import ChatMessage, AIUsageLog, LegalDraft

@login_required
@require_POST
def authorize_ai(request):
    """
    Handles the Mandatory Compliance Check.
    """
    complaint_no = request.POST.get('complaint_no')
    justification = request.POST.get('justification')
    
    if complaint_no and justification:
        # Log it
        AIUsageLog.objects.create(
            user=request.user,
            complaint_no=complaint_no,
            justification=justification,
            session_id=request.session.session_key
        )
        
        # Authorize Session
        request.session['ai_authorized'] = True
        return redirect('ai_lab')
    
    return redirect('officer_dashboard')

@login_required
@require_POST
def generate_legal(request):
    """
    Generates a legal writeup via AI and returns a PDF.
    """
    try:
        data = json.loads(request.body)
        ref_no = data.get('reference_no')
        justification = data.get('justification')
        
        if not ref_no or not justification:
            return JsonResponse({'error': 'Missing fields'}, status=400)
            
        doc_content = TrinetraAI.generate_legal_doc(ref_no, justification, None)
        
        # Save Draft (using the JSON content for record)
        LegalDraft.objects.create(
            user=request.user,
            reference_no=ref_no,
            justification=justification,
            generated_content=json.dumps(doc_content)
        )

        # Generate PDF
        buffer = io.BytesIO()
        generate_professional_pdf(doc_content, buffer)
        buffer.seek(0)
        
        return FileResponse(buffer, as_attachment=True, filename=f"Legal_Opinion_{ref_no}.pdf")

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def ai_lab(request):
    """
    Dedicated AI Lab View.
    fetches chat history and renders the AI interface.
    """
    # Verify Cert
    is_cert_valid, _ = verify_client_certificate(request)
    if not is_cert_valid:
        return redirect('portal_login')
    
    # NEW LOGIC: Require valid Case ID
    case_id = request.GET.get('case_id')
    active_case = None
    
    if case_id:
        try:
            active_case = Case.objects.get(case_no=case_id)
            # Optional: Check if officer has access? For now, open to all officers.
        except Case.DoesNotExist:
            return redirect('officer_dashboard')
    else:
        # Fallback to old "Authorized Session" check if no case_id (Legacy support)
        if not request.session.get('ai_authorized'):
             return redirect('officer_dashboard')

    
    # Initialize Context
    context = {
        'user': request.user,
    }

    history = ChatMessage.objects.filter(user=request.user)
    
    if active_case:
        history = history.filter(case=active_case)
        context['case_id'] = active_case.case_no
        
    history = history.order_by('-timestamp')[:20]
    context['history'] = history
    
    return render(request, 'officer_portal/ai_lab.html', context)

@login_required
@require_POST
def create_case_endpoint(request):
    """
    API Endpoint to create a new case from the dashboard.
    """
    try:
        data = json.loads(request.body)
        suspect_name = data.get('suspect_name')
        description = data.get('description')
        priority = data.get('priority', 'MEDIUM')
        
        if not suspect_name or not description:
            return JsonResponse({'error': 'Missing required fields'}, status=400)
            
        # Create Case in DB
        idx = Case.objects.count() + 1
        date_str = datetime.now().strftime("%Y%m%d")
        case_no = f"CASE-{date_str}-{idx:04d}"
        
        Case.objects.create(
            case_no=case_no,
            officer=request.user,
            suspect_name=suspect_name,
            description=description,
            priority=priority,
            status='OPEN'
        )
        
        # Sync with AI Node (Optional but recommended)
        try:
            # Sync with AI Node
            from . import ai_service
            ai_service.fetch_or_create_case(case_no, justification=description)
        except Exception as e:
            logger.warning(f"AI Sync failed for {case_no}: {e}")
            
        return JsonResponse({'message': 'Case created successfully', 'case_no': case_no})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error creating case: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def download_case_pdf(request):
    """
    Generate a legal PDF for a specific case using AI.
    """
    case_id = request.GET.get('case_id')
    if not case_id:
        return JsonResponse({'error': 'Case ID required'}, status=400)
        
    try:
        # Fetch Local Case Data
        case = Case.objects.filter(case_no=case_id).first()
        if not case:
            return JsonResponse({'error': 'Case not found'}, status=404)
            
        # Prepare Context for AI
        # We constructed a prompt based on local data to ensure AI has context
        facts = f"Suspect: {case.suspect_name}\nIncident Description: {case.description}\nPriority: {case.priority}"
        
        # Call AI Service
        from . import ai_service
        ai_data = ai_service.generate_legal_doc(case_id, facts=facts)
        
        # If AI returns error or empty, fallback to basic data
        if 'error' in ai_data:
            logger.warning(f"AI Generation failed: {ai_data['error']}")
            # Fallback structure
            ai_data = {
                'case_id': case_id,
                'title': f'Investigation Report - {case.suspect_name}',
                'facts': case.description,
                'analysis': 'AI Analysis Module Unavailable - Manual input required.',
                'conclusion': 'Pending Review',
                'date': datetime.now().strftime("%d-%b-%Y")
            }
        else:
            # Ensure case_id is in data
            ai_data['case_id'] = case_id
            
        # Generate PDF
        from . import pdf_utils
        buffer = BytesIO()
        pdf_utils.generate_professional_pdf(ai_data, buffer)
        
        buffer.seek(0)
        filename = f"Legal_Opinion_{case_id}.pdf"
        
        return FileResponse(buffer, as_attachment=True, filename=filename)

    except Exception as e:
        logger.error(f"PDF Generation Error: {e}")
        return JsonResponse({'error': str(e)}, status=500)
