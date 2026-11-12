"""
Row level security on every table in the public schema.

A hosted PostgreSQL may expose the public schema over HTTP (Supabase's Data API
does, for its anon and authenticated roles). Enabling RLS without policies
denies those roles everything, while Django, which connects as the table
owner, is unaffected. This runs after every `migrate`, so tables added by any
app or module are covered automatically; core.tests.test_database checks it.
"""

import logging

from django.db import connections

logger = logging.getLogger('security')

TABLES_WITHOUT_RLS = """
    SELECT c.relname
    FROM pg_class c
    WHERE c.relnamespace = 'public'::regnamespace
      AND c.relkind IN ('r', 'p')
      AND NOT c.relrowsecurity
    ORDER BY c.relname
"""


def tables_without_rls(connection):
    with connection.cursor() as cursor:
        cursor.execute(TABLES_WITHOUT_RLS)
        return [row[0] for row in cursor.fetchall()]


def enable_row_level_security(using='default', **kwargs):
    connection = connections[using]
    if connection.vendor != 'postgresql':
        return
    tables = tables_without_rls(connection)
    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f'ALTER TABLE {connection.ops.quote_name(table)} ENABLE ROW LEVEL SECURITY')
    if tables:
        logger.info('rls.enabled tables=%s', ','.join(tables))
