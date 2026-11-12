"""The CRM in the admin: pipeline, actions, exports, tasks, and two-factor protection."""

import csv
import io
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from crm.exports import safe_cell
from crm.models import Contact, Interaction, Task

User = get_user_model()
PASSWORD = 'correct-Horse-battery-42'


@override_settings(STAFF_MFA_REQUIRED=False)
class ContactAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('owner', 'o@example.com', PASSWORD)
        self.client.force_login(self.admin)
        self.contact = Contact.objects.create(name='Ana', email='ana@example.com', phone='=HYPERLINK("http://x")')
        self.changelist = reverse('admin:crm_contact_changelist')

    def action(self, name, ids):
        return self.client.post(self.changelist, {'action': name, '_selected_action': ids})

    def test_pipeline_list_shows_stage_counts(self):
        response = self.client.get(self.changelist)
        self.assertContains(response, 'Ana')
        self.assertContains(response, 'New (1)')

    def test_stage_action_moves_contacts(self):
        self.action('move_to_quoted', [self.contact.pk])
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.stage, Contact.Stage.QUOTED)

    def test_csv_export_neutralizes_spreadsheet_formulas(self):
        response = self.action('export_csv', [self.contact.pk])
        rows = list(csv.reader(io.StringIO(b''.join(response.streaming_content).decode())))
        self.assertEqual(rows[0][0], 'Name')
        self.assertEqual(rows[1][2], '\'=HYPERLINK("http://x")')

    def test_personal_data_export_includes_the_timeline(self):
        Interaction.objects.create(contact=self.contact, summary='Called back', kind=Interaction.Kind.CALL)
        response = self.action('export_personal_data', [self.contact.pk])
        data = json.loads(response.content)
        self.assertEqual(data['contact']['email'], 'ana@example.com')
        self.assertEqual(data['timeline'][0]['summary'], 'Called back')

    def test_notes_added_inline_record_the_author(self):
        url = reverse('admin:crm_contact_change', args=[self.contact.pk])
        page = self.client.get(url)
        form = page.context['adminform'].form
        data = {
            **{key: value for key, value in form.initial.items() if value is not None and key != 'tags'},
            'interactions-TOTAL_FORMS': 1,
            'interactions-INITIAL_FORMS': 0,
            'interactions-0-kind': 'note',
            'interactions-0-summary': 'Prefers mornings',
            'interactions-0-occurred_at_0': timezone.localdate().isoformat(),
            'interactions-0-occurred_at_1': '09:00:00',
            'tasks-TOTAL_FORMS': 0,
            'tasks-INITIAL_FORMS': 0,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, response.context and response.context['errors'])
        self.assertEqual(Interaction.objects.get(summary='Prefers mornings').author, self.admin)

    def test_exports_need_permission(self):
        clerk = User.objects.create_user('clerk', 'c@example.com', PASSWORD, is_staff=True)
        clerk.user_permissions.add(Permission.objects.get(codename='view_task'))
        self.client.force_login(clerk)
        self.assertEqual(self.action('export_csv', [self.contact.pk]).status_code, 403)


@override_settings(STAFF_MFA_REQUIRED=False)
class TaskAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('owner', 'o@example.com', PASSWORD))
        contact = Contact.objects.create(name='Ana')
        today = timezone.localdate()
        Task.objects.create(contact=contact, title='Overdue call', due_date=today - timedelta(days=2))
        Task.objects.create(contact=contact, title='Next week', due_date=today + timedelta(days=7))

    def test_overdue_filter(self):
        response = self.client.get(reverse('admin:crm_task_changelist') + '?due=overdue')
        self.assertContains(response, 'Overdue call')
        self.assertNotContains(response, 'Next week')

    def test_completing_a_task_records_when(self):
        task = Task.objects.get(title='Next week')
        self.client.post(reverse('admin:crm_task_changelist'), {'action': 'mark_done', '_selected_action': [task.pk]})
        task.refresh_from_db()
        self.assertTrue(task.done)
        self.assertIsNotNone(task.done_at)


class CrmProtectionTests(TestCase):
    def test_crm_turns_on_staff_two_factor_by_default(self):
        from django.conf import settings

        self.assertTrue(settings.STAFF_MFA_REQUIRED)

    @override_settings(STAFF_MFA_REQUIRED=True)
    def test_unverified_staff_cannot_open_contacts(self):
        self.client.force_login(User.objects.create_superuser('owner', 'o@example.com', PASSWORD))
        response = self.client.get(reverse('admin:crm_contact_changelist'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('mfa_setup')))

    def test_safe_cell(self):
        for value, expected in (('=1+1', "'=1+1"), ('+33 1', "'+33 1"), ('Ana', 'Ana'), (None, '')):
            with self.subTest(value=value):
                self.assertEqual(safe_cell(value), expected)
