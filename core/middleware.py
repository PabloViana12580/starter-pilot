import time
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import reverse

from .mfa import pending_step

SESSION_STARTED_KEY = 'core_session_started'


class PermissionsPolicyMiddleware:
    """Adds the Permissions-Policy header (browser features this site never uses)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.PERMISSIONS_POLICY:
            response.headers.setdefault('Permissions-Policy', settings.PERMISSIONS_POLICY)
        return response


class SessionLifetimeMiddleware:
    """Ends signed-in sessions SESSION_ABSOLUTE_TIMEOUT_SECONDS after login, even if active."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            started = request.session.setdefault(SESSION_STARTED_KEY, int(time.time()))
            if time.time() - started > settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS:
                logout(request)
                return redirect_to_login(request.get_full_path())
        return self.get_response(request)


class StaffMFAMiddleware:
    """
    Until a staff member passes the second factor, every page except the
    two-factor steps, sign-out, probes, and static files sends them to that step.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        step = pending_step(request.user)
        if step and not self._always_allowed(request.path):
            return redirect(f'{reverse(step)}?{urlencode({"next": request.get_full_path()})}')
        return self.get_response(request)

    @staticmethod
    def _always_allowed(path):
        allowed = (
            reverse('mfa_setup'),
            reverse('mfa_verify'),
            reverse('logout'),
            reverse('csp_report'),
            '/' + settings.STATIC_URL.lstrip('/'),
        )
        return path.startswith(allowed) or path in ('/healthz', '/readyz')
