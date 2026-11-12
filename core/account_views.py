"""Staff sign-in with lockout (django-axes), two-factor login (django-otp), and sign-out."""

import base64
import logging
from urllib.parse import urlencode

import django_otp
from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django_otp.plugins.otp_totp.models import TOTPDevice

from .mfa import mfa_satisfied, pending_step, qr_svg
from .net import client_ip

logger = logging.getLogger('security')

MAX_TOKEN_FAILURES = 5
FAILURES_KEY = 'core_mfa_failures'


class TokenForm(forms.Form):
    token = forms.CharField(
        label=gettext_lazy('Code'),
        max_length=16,
        widget=forms.TextInput(
            attrs={
                'autocomplete': 'one-time-code',
                'inputmode': 'numeric',
                'autocapitalize': 'none',
                'spellcheck': 'false',
                'autofocus': True,
            }
        ),
    )

    def clean_token(self):
        return ''.join(self.cleaned_data['token'].split())


class StaffLoginView(LoginView):
    """
    Password step of staff sign-in. Afterwards staff continue to the two-factor
    step when it applies; accounts without staff access go to the home page
    (the admin would only send them back here).
    """

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and user.is_staff and pending_step(user) is None:
            return redirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        user = self.request.user
        step = pending_step(user)
        if step:
            return f'{reverse(step)}?{urlencode({"next": self.get_redirect_url()})}'
        if not user.is_staff:
            return '/'
        return super().get_success_url()


def _next_url(request):
    candidate = request.POST.get('next') or request.GET.get('next') or ''
    if url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return candidate
    return reverse('admin:index')


def _count_failure(request):
    """Returns True when the session has used up its attempts and was signed out."""
    failures = request.session.get(FAILURES_KEY, 0) + 1
    request.session[FAILURES_KEY] = failures
    logger.warning('mfa.failed user_id=%s ip=%s failures=%s', request.user.pk, client_ip(request), failures)
    if failures >= MAX_TOKEN_FAILURES:
        logout(request)
        return True
    return False


@never_cache
@login_required
def mfa_setup(request):
    """First sign-in of a staff member: connect an authenticator app."""
    if mfa_satisfied(request.user):
        return redirect(_next_url(request))
    if pending_step(request.user) == 'mfa_verify':
        # A device already exists; adding another needs the current one.
        return redirect(f'{reverse("mfa_verify")}?{urlencode({"next": _next_url(request)})}')

    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(user=request.user, name=_('Authenticator app'), confirmed=False)

    form = TokenForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if device.verify_token(form.cleaned_data['token']):
            device.confirmed = True
            device.save(update_fields=['confirmed'])
            django_otp.login(request, device)
            request.session.pop(FAILURES_KEY, None)
            logger.info('mfa.enrolled user_id=%s ip=%s', request.user.pk, client_ip(request))
            messages.success(request, _('Two-factor sign-in is on. If you lose your phone, ask an administrator to reset it.'))
            return redirect(_next_url(request))
        if _count_failure(request):
            return redirect('login')
        form.add_error('token', _('That code is not valid. Check the time on your phone and try again.'))

    return render(
        request,
        'core/mfa_setup.html',
        {
            'form': form,
            'qr_svg': qr_svg(device.config_url),
            'secret': _base32(device.bin_key),
            'next': _next_url(request),
        },
    )


@never_cache
@login_required
def mfa_verify(request):
    """Every staff sign-in: enter the current code from the authenticator app."""
    if mfa_satisfied(request.user):
        return redirect(_next_url(request))
    if pending_step(request.user) == 'mfa_setup':
        return redirect(f'{reverse("mfa_setup")}?{urlencode({"next": _next_url(request)})}')

    form = TokenForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        device = django_otp.match_token(request.user, form.cleaned_data['token'])
        if device is not None:
            django_otp.login(request, device)
            request.session.pop(FAILURES_KEY, None)
            logger.info('mfa.verified user_id=%s ip=%s device=%s', request.user.pk, client_ip(request), type(device).__name__)
            return redirect(_next_url(request))
        if _count_failure(request):
            return redirect('login')
        form.add_error('token', _('That code is not valid. Enter the newest code your app shows.'))

    return render(request, 'core/mfa_verify.html', {'form': form, 'next': _next_url(request)})


def _base32(key):
    return base64.b32encode(key).decode('ascii').rstrip('=')


class StaffLogoutView(LogoutView):
    """Sign-out (POST only) that also tells the browser to clear this site's stored data."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response['Clear-Site-Data'] = '"cache", "cookies", "storage"'
        return response
