"""Two-factor login rules for staff (TOTP authenticator apps via django-otp)."""

import io

import qrcode
import qrcode.image.svg
from django.conf import settings
from django_otp import user_has_device


def mfa_required(user):
    """Staff and superusers must pass a second factor when STAFF_MFA_REQUIRED is on."""
    return settings.STAFF_MFA_REQUIRED and user.is_authenticated and (user.is_staff or user.is_superuser)


def mfa_satisfied(user):
    # OTPMiddleware sets `otp_device` on request.user; a user fresh from the login form has none yet.
    return not mfa_required(user) or getattr(user, 'otp_device', None) is not None


def pending_step(user):
    """URL name of the two-factor step this user still needs, or None."""
    if mfa_satisfied(user):
        return None
    return 'mfa_verify' if user_has_device(user) else 'mfa_setup'


def qr_svg(data):
    """An inline SVG QR code for `data` (no images, so it works under the CSP)."""
    image = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    svg = buffer.getvalue().decode('utf-8')
    # Drop the XML declaration so the SVG can sit inside HTML.
    return svg[svg.index('<svg') :]
