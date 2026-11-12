import json
import logging

from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .spam import rate_limited

security_log = logging.getLogger('security')

CSP_REPORT_MAX_BYTES = 10_000
CSP_REPORT_FIELDS = ('document-uri', 'violated-directive', 'effective-directive', 'blocked-uri', 'source-file', 'line-number')


@require_GET
def healthz(request):
    """Liveness: the process answers. No login, no database."""
    return HttpResponse('ok', content_type='text/plain')


@require_GET
def readyz(request):
    """Readiness: the database answers too. 503 tells the platform not to route traffic yet."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except DatabaseError:
        security_log.error('readyz.database_unavailable')
        return HttpResponse('database unavailable', status=503, content_type='text/plain')
    return HttpResponse('ready', content_type='text/plain')


@csrf_exempt  # browsers send violation reports without a CSRF token
@require_POST
def csp_report(request):
    """Logs Content Security Policy violations reported by browsers (rate limited)."""
    if len(request.body) <= CSP_REPORT_MAX_BYTES and not rate_limited(request, 'csp-report', limit=30, window=60):
        try:
            report = json.loads(request.body).get('csp-report', {})
        except (ValueError, AttributeError):
            report = {}
        if isinstance(report, dict):
            fields = ' '.join(f'{key}={str(report.get(key, ""))[:200]!r}' for key in CSP_REPORT_FIELDS)
            security_log.warning('csp.violation %s', fields)
    return HttpResponse(status=204)


@require_GET
def index(request):
    """Home page used only when no module provides one."""
    return render(request, 'core/index.html')
