"""Contact exports: a CSV for spreadsheets and a full per-person data export (privacy requests)."""

import csv
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone

CSV_COLUMNS = [
    ('name', 'Name'),
    ('email', 'Email'),
    ('phone', 'Phone'),
    ('company', 'Company'),
    ('stage', 'Stage'),
    ('source', 'Source'),
    ('tags', 'Tags'),
    ('marketing_consent', 'Agreed to news and offers'),
    ('consent_updated_at', 'Consent changed'),
    ('created_at', 'Created'),
]

# Cells starting with these are run as formulas by spreadsheet apps (CSV injection).
FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def safe_cell(value):
    text = '' if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


class _Echo:
    def write(self, value):
        return value


def contact_rows(queryset):
    yield [label for _field, label in CSV_COLUMNS]
    for contact in queryset.prefetch_related('tags'):
        values = {
            'name': contact.name,
            'email': contact.email,
            'phone': contact.phone,
            'company': contact.company,
            'stage': contact.get_stage_display(),
            'source': contact.get_source_display(),
            'tags': ', '.join(tag.name for tag in contact.tags.all()),
            'marketing_consent': 'yes' if contact.marketing_consent else 'no',
            'consent_updated_at': contact.consent_updated_at.isoformat() if contact.consent_updated_at else '',
            'created_at': contact.created_at.isoformat(),
        }
        yield [safe_cell(values[field]) for field, _label in CSV_COLUMNS]


def contacts_csv_response(queryset):
    writer = csv.writer(_Echo())
    response = StreamingHttpResponse(
        (writer.writerow(row) for row in contact_rows(queryset)),
        content_type='text/csv; charset=utf-8',
    )
    stamp = timezone.localtime().strftime('%Y%m%d-%H%M')
    response['Content-Disposition'] = f'attachment; filename="contacts-{stamp}.csv"'
    return response


def contact_data(contact):
    """Everything stored about one person, for a data access request."""
    return {
        'contact': {
            'name': contact.name,
            'email': contact.email,
            'phone': contact.phone,
            'company': contact.company,
            'stage': contact.stage,
            'source': contact.source,
            'tags': [tag.name for tag in contact.tags.all()],
            'marketing_consent': contact.marketing_consent,
            'consent_updated_at': contact.consent_updated_at,
            'consent_source': contact.consent_source,
            'created_at': contact.created_at,
            'updated_at': contact.updated_at,
        },
        'timeline': [
            {'type': entry.kind, 'summary': entry.summary, 'details': entry.body, 'when': entry.occurred_at}
            for entry in contact.interactions.all()
        ],
        'tasks': [{'task': task.title, 'due': task.due_date, 'done': task.done} for task in contact.tasks.all()],
    }


def contact_data_response(contact):
    body = json.dumps(contact_data(contact), cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)
    response = HttpResponse(body, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="contact-{contact.pk}.json"'
    return response
