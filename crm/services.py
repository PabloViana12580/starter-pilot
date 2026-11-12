"""
CRM operations used by the contact form and by other modules (orders,
appointments). Other modules call these instead of touching CRM models, so
the CRM stays the single place where contacts are created and matched.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from core.notifications import send_notification

from .models import Contact, Interaction

logger = logging.getLogger(__name__)


def find_contact_by_email(email):
    email = (email or '').strip()
    if not email:
        return None
    return Contact.objects.filter(email__iexact=email).first()


@transaction.atomic
def upsert_contact(*, name, email='', phone='', source=Contact.Source.MANUAL, consent=None, consent_source=''):
    """
    The contact with this email (ignoring case), updated with any details it
    was missing, or a new one. Returns (contact, created). Existing names and
    phone numbers are never overwritten by public form input.
    """
    email = (email or '').strip()
    contact = Contact.objects.select_for_update().filter(email__iexact=email).first() if email else None
    created = contact is None
    if created:
        contact = Contact(name=name.strip(), email=email, phone=phone.strip(), source=source)
    else:
        contact.name = contact.name or name.strip()
        contact.phone = contact.phone or phone.strip()
    if consent is not None:
        contact.set_consent(consent, consent_source or source)
    contact.save()
    return contact, created


def record_interaction(contact, *, kind, summary, body='', author=None):
    return Interaction.objects.create(contact=contact, kind=kind, summary=summary[:200], body=body, author=author)


def submit_inquiry(*, name, email, phone, message, marketing_consent):
    """A message from the website's contact form: contact, timeline entry, owner email."""
    # A ticked box records consent. An unticked box records "no" for a new
    # contact, but never withdraws consent given on an earlier message.
    known = find_contact_by_email(email) is not None
    contact, created = upsert_contact(
        name=name,
        email=email,
        phone=phone,
        source=Contact.Source.CONTACT_FORM,
        consent=True if marketing_consent else (None if known else False),
        consent_source='Website contact form',
    )
    interaction = record_interaction(
        contact,
        kind=Interaction.Kind.FORM,
        summary=f'Website message from {name}'[:200],
        body=message,
    )
    admin_path = reverse('admin:crm_contact_change', args=[contact.pk])
    send_notification(
        subject=f'New message from {name} ({settings.SITE_NAME})',
        template='crm/emails/new_inquiry.txt',
        context={
            'contact': contact,
            'message': message,
            'created': created,
            'admin_url': settings.SITE_URL + admin_path,
        },
        to=settings.CRM_NOTIFY_EMAILS,
    )
    logger.info('crm.inquiry contact=%s new=%s', contact.pk, created)
    return contact, interaction
