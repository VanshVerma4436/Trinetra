from django.conf import settings
from django.http import HttpResponseForbidden
from access_control.models import AllowedStation
from access_control.utils import get_client_ip
from django.utils import timezone
from access_control.models import TrapLog

class IPFortressMiddleware:
    """
    Blocks access from unauthorized IP addresses.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, 'TRINETRA_STRICT_FIREWALL', False):
            return self.get_response(request)

        client_ip = get_client_ip(request)
        
        if AllowedStation.objects.filter(static_ip=client_ip, is_active=True).exists():
             return self.get_response(request)

        TrapLog.objects.create(
            ip_address=client_ip,
            attempted_username=request.user.username if request.user.is_authenticated else 'Anonymous',
            user_agent=request.META.get('HTTP_USER_AGENT', 'Unknown'),
            timestamp=timezone.now()
        )
        return HttpResponseForbidden(f"TRINETRA FIREWALL: ACCESS DENIED ({client_ip})")
