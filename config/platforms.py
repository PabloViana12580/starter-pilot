"""
Public host names published by hosting platforms through environment variables.

Settings add these to ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS, so a deployment
on one of these platforms needs no host configuration until it gets a custom
domain. Any other platform works the same way through DJANGO_ALLOWED_HOSTS and
DJANGO_CSRF_TRUSTED_ORIGINS.
"""

# Platform name: (environment variable, host name pattern).
PLATFORM_HOSTNAME_VARIABLES = {
    'Render': ('RENDER_EXTERNAL_HOSTNAME', '{}'),
    'Railway': ('RAILWAY_PUBLIC_DOMAIN', '{}'),
    'Fly.io': ('FLY_APP_NAME', '{}.fly.dev'),
    'Azure App Service': ('WEBSITE_HOSTNAME', '{}'),
}


def platform_hostnames(environ):
    """Host names found in `environ` (a mapping like os.environ)."""
    hosts = []
    for variable, pattern in PLATFORM_HOSTNAME_VARIABLES.values():
        value = environ.get(variable, '').strip()
        if value:
            hosts.append(pattern.format(value))
    return hosts
