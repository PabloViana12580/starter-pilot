from django.conf import settings


def client_ip(request):
    """
    The client's address, trusting X-Forwarded-For only as far as configured.

    With TRUSTED_PROXY_COUNT = n, the n-th address from the right of
    X-Forwarded-For is used (each trusted proxy appends the address it saw);
    with 0, only the direct connection is trusted. Used by login lockout and
    by rate limits.
    """
    proxies = settings.TRUSTED_PROXY_COUNT
    if proxies > 0:
        forwarded = [part.strip() for part in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if part.strip()]
        if len(forwarded) >= proxies:
            return forwarded[-proxies]
    return request.META.get('REMOTE_ADDR', '')
