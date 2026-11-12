"""CRM services: matching contacts, consent records, website messages, owner email."""

from unittest import mock

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from crm.models import Contact, Interaction
from crm.services import submit_inquiry, upsert_contact


class UpsertContactTests(TestCase):
    def test_creates_then_matches_by_email_ignoring_case(self):
        first, created = upsert_contact(name='Ana Ruiz', email='Ana@Example.com', source=Contact.Source.CONTACT_FORM)
        again, created_again = upsert_contact(name='Someone Else', email='ana@example.com')
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(again.name, 'Ana Ruiz')  # public input never overwrites existing details

    def test_fills_in_missing_details(self):
        upsert_contact(name='Ana', email='ana@example.com')
        contact, _created = upsert_contact(name='Ana', email='ana@example.com', phone='555-0100')
        self.assertEqual(contact.phone, '555-0100')

    def test_email_is_unique_ignoring_case_in_the_database(self):
        Contact.objects.create(name='A', email='same@example.com')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Contact.objects.create(name='B', email='SAME@example.com')
        Contact.objects.create(name='No email 1')
        Contact.objects.create(name='No email 2')  # contacts without email are allowed

    def test_consent_records_when_and_how(self):
        contact, _created = upsert_contact(
            name='Ana',
            email='ana@example.com',
            consent=True,
            consent_source='Website contact form',
        )
        self.assertTrue(contact.marketing_consent)
        self.assertIsNotNone(contact.consent_updated_at)
        self.assertEqual(contact.consent_source, 'Website contact form')


@override_settings(CRM_NOTIFY_EMAILS=['owner@example.com'], SITE_URL='https://shop.example.com')
class SubmitInquiryTests(TestCase):
    def submit(self, **overrides):
        data = {
            'name': 'Ana',
            'email': 'ana@example.com',
            'phone': '',
            'message': 'Do you work weekends?',
            'marketing_consent': False,
        }
        return submit_inquiry(**{**data, **overrides})

    def test_creates_lead_timeline_entry_and_owner_email(self):
        contact, interaction = self.submit()
        self.assertEqual((contact.stage, contact.source), (Contact.Stage.NEW, Contact.Source.CONTACT_FORM))
        self.assertEqual(interaction.kind, Interaction.Kind.FORM)
        self.assertEqual(interaction.body, 'Do you work weekends?')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['owner@example.com'])
        self.assertIn(f'https://shop.example.com/admin/crm/contact/{contact.pk}/change/', mail.outbox[0].body)

    def test_unticked_box_on_a_later_message_keeps_earlier_consent(self):
        self.submit(marketing_consent=True)
        contact, _interaction = self.submit(marketing_consent=False)
        self.assertTrue(contact.marketing_consent)

    def test_mail_outage_does_not_lose_the_message(self):
        with (
            mock.patch('core.notifications.send_mail', side_effect=OSError('smtp down')),
            self.assertLogs('core.notifications', 'ERROR'),
        ):
            contact, _interaction = self.submit()
        self.assertTrue(Interaction.objects.filter(contact=contact).exists())

    def test_subject_cannot_carry_header_injection(self):
        self.submit(name='Ana\r\nBcc: victim@example.com')
        self.assertNotIn('\n', mail.outbox[0].subject)
