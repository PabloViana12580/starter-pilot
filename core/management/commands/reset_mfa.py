import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp import devices_for_user

logger = logging.getLogger('security')


class Command(BaseCommand):
    help = (
        "Removes a user's two-factor devices (lost or replaced phone), so they set up "
        'a new authenticator app at their next sign-in. Confirm who is asking before '
        'running it. Staff with access can also delete the device in the admin.'
    )

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, *args, username, **options):
        User = get_user_model()
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: username})
        except User.DoesNotExist as exc:
            raise CommandError(f'No user named {username!r}.') from exc
        devices = list(devices_for_user(user, confirmed=None))
        for device in devices:
            device.delete()
        logger.warning('mfa.reset user_id=%s devices=%s via=command', user.pk, len(devices))
        self.stdout.write(
            self.style.SUCCESS(
                f'Removed {len(devices)} device(s). {username} sets up two-factor sign-in again at the next sign-in.'
            )
        )
