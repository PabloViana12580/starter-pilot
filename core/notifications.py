import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def single_line(text, limit=120):
    """Text safe for an email subject: one line, bounded length."""
    return ' '.join(str(text).split())[:limit]


def send_notification(*, subject, template, context, to):
    """
    Send a plain-text email rendered from `template`. Returns False instead of
    raising when delivery fails, so a mail outage never loses the data that
    triggered the email; failures are logged.
    """
    recipients = [address for address in to if address]
    if not recipients:
        return False
    body = render_to_string(template, context)
    try:
        send_mail(single_line(subject), body, None, recipients)
    except Exception:
        logger.exception('email.failed template=%s', template)
        return False
    return True
