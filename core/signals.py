"""Security event logging: sign-in, sign-out, failures, and lockouts. Never passwords."""

import logging

from axes.signals import user_locked_out
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .net import client_ip

logger = logging.getLogger('security')


def _ip(request):
    return client_ip(request) if request is not None else ''


@receiver(user_logged_in, dispatch_uid='core.log_login')
def log_login(sender, request, user, **kwargs):
    logger.info('auth.login user_id=%s ip=%s', user.pk, _ip(request))


@receiver(user_logged_out, dispatch_uid='core.log_logout')
def log_logout(sender, request, user, **kwargs):
    logger.info('auth.logout user_id=%s ip=%s', getattr(user, 'pk', None), _ip(request))


@receiver(user_login_failed, dispatch_uid='core.log_login_failed')
def log_login_failed(sender, credentials, request=None, **kwargs):
    # Only the username: Django already masks the password in `credentials`,
    # and nothing else from them is logged.
    logger.warning('auth.login_failed username=%r ip=%s', credentials.get('username', ''), _ip(request))


@receiver(user_locked_out, dispatch_uid='core.log_locked_out')
def log_locked_out(sender, request, username, ip_address, **kwargs):
    logger.warning('auth.locked_out username=%r ip=%s', username, ip_address)
