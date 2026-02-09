from django.shortcuts import render, redirect
from django.conf import settings
from .utils import get_client_ip
from .models import AllowedStation

def trap_login(request):
    """
    The view for the trap login page.
    This might be reached via redirect or direct access, 
    but Middleware handles the forced rendering for blocked IPs.
    """
    return render(request, 'trap_login.html')

def root_routing_view(request):
    """
    Smart Redirect based on IP Authorization.
    - Authorized IP -> Officer Portal Login
    - Unauthorized IP -> Trap Login
    """
    client_ip = get_client_ip(request)
    
    # Check if IP is explicitly allowed (Whitelist) OR if we are in Dev Mode
    if getattr(settings, 'DEBUG', False) or \
       not getattr(settings, 'TRINETRA_STRICT_FIREWALL', False) or \
       AllowedStation.objects.filter(static_ip=client_ip, is_active=True).exists():
        # Authorized: Send to real portal
        return redirect('portal_login') 
    else:
        # Unauthorized: Send to honeypot
        return redirect('trap_login')
