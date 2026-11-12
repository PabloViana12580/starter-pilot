"""
Spam protection for public forms: a honeypot field, a minimum fill-in time,
and per-address rate limits. Rejections are logged on the "security" logger.
"""

import logging
import time

from django import forms
from django.core import signing
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from .net import client_ip

logger = logging.getLogger('security')

SIGNER_SALT = 'core.spam.form-started'


def rate_limited(request, scope, *, limit, window):
    """
    Count one request for this client in `scope`; True once more than `limit`
    happened within `window` seconds. Uses the default cache (per process).
    """
    key = f'ratelimit:{scope}:{client_ip(request)}'
    if cache.add(key, 1, timeout=window):
        return False
    try:
        count = cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.add(key, 1, timeout=window)
        return False
    return count > limit


class SpamProtectedForm(forms.Form):
    """
    Base for public forms. `website` is a honeypot people never see (bots fill
    it in); `started` carries a signed timestamp so forms submitted faster than
    MIN_SECONDS, or older than MAX_AGE_SECONDS, are treated as automated.
    """

    MIN_SECONDS = 3
    MAX_AGE_SECONDS = 24 * 60 * 60

    website = forms.CharField(
        required=False,
        label=_('Leave this field empty'),
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'tabindex': '-1'}),
    )
    started = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial['started'] = signing.TimestampSigner(salt=SIGNER_SALT).sign(str(int(time.time())))

    def spam_reason(self):
        """Why this submission looks automated, or '' (call after is_valid())."""
        if self.data.get('website'):
            return 'honeypot'
        try:
            started = int(
                signing.TimestampSigner(salt=SIGNER_SALT).unsign(self.data.get('started', ''), max_age=self.MAX_AGE_SECONDS)
            )
        except (signing.BadSignature, ValueError):
            return 'bad_timestamp'
        if time.time() - started < self.MIN_SECONDS:
            return 'too_fast'
        return ''


def log_spam(request, form_name, reason):
    logger.warning('spam.rejected form=%s reason=%s ip=%s', form_name, reason, client_ip(request))
