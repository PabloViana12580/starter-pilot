from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core.rls import tables_without_rls

LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}


class Command(BaseCommand):
    help = (
        'Checks the configured database: connection, TLS, privileges, row level '
        'security, and that it holds no tables from another project.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--before-migrate',
            action='store_true',
            help='Skip the row level security check (tables do not exist yet).',
        )

    def handle(self, *args, before_migrate=False, **options):
        problems = []
        host = settings.DATABASES['default']['HOST']

        with connection.cursor() as cursor:
            cursor.execute('SHOW server_version')
            version = cursor.fetchone()[0]
            cursor.execute('SELECT current_user, current_database()')
            user, database = cursor.fetchone()
            cursor.execute('SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user')
            row = cursor.fetchone()
            can_create_db = bool(row and row[0])
        self.stdout.write(f'Connected: PostgreSQL {version}, database {database!r} as {user!r}.')

        ssl_in_use = bool(connection.connection.pgconn.ssl_in_use)
        if ssl_in_use:
            self.stdout.write('TLS: in use.')
        elif host in LOCAL_HOSTS:
            self.stdout.write('TLS: not in use (accepted for a local server).')
        else:
            problems.append('The connection is not encrypted (TLS). Use sslmode=require or stricter.')

        if can_create_db:
            self.stdout.write('Privileges: can create the temporary test database.')
        else:
            self.stdout.write(
                self.style.WARNING(
                    'Privileges: this role cannot create databases, so `manage.py test` will fail '
                    'against this server. See docs/DEVELOPER.md "Tests".'
                )
            )

        if host.startswith('db.') and host.endswith('.supabase.co'):
            self.stdout.write(
                self.style.WARNING(
                    "Supabase's direct host is IPv6-only and unreachable from many networks and hosts. "
                    'Prefer the Session pooler URI (Dashboard > Connect > Session pooler).'
                )
            )

        project_tables = set(connection.introspection.django_table_names(include_views=False))
        project_tables.add('django_migrations')
        foreign = sorted(set(connection.introspection.table_names()) - project_tables)
        if foreign:
            problems.append(
                'This database holds tables that do not belong to this project: '
                + ', '.join(foreign[:10])
                + ('...' if len(foreign) > 10 else '')
                + '. Each project needs its own database.'
            )
        else:
            self.stdout.write('Isolation: no tables from other projects.')

        if not before_migrate:
            missing = tables_without_rls(connection)
            if missing:
                problems.append('Row level security is off for: ' + ', '.join(missing) + '. Run migrate.')
            else:
                self.stdout.write('Row level security: on for every table.')

        if problems:
            raise CommandError('\n'.join(problems))
        self.stdout.write(self.style.SUCCESS('Database check passed.'))
