import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Tag(models.Model):
    name = models.CharField(_('name'), max_length=50)

    class Meta:
        ordering = ['name']
        verbose_name = _('tag')
        verbose_name_plural = _('tags')
        constraints = [models.UniqueConstraint(Lower('name'), name='crm_tag_name_ci_unique')]

    def __str__(self):
        return self.name


class Contact(models.Model):
    """A person the business deals with: a lead until they buy or book, then a customer."""

    class Stage(models.TextChoices):
        NEW = 'new', _('New')
        CONTACTED = 'contacted', _('Contacted')
        QUOTED = 'quoted', _('Quoted')
        WON = 'won', _('Won')
        LOST = 'lost', _('Lost')

    class Source(models.TextChoices):
        CONTACT_FORM = 'contact_form', _('Website contact form')
        MANUAL = 'manual', _('Added by staff')
        IMPORT = 'import', _('Imported')
        ORDER = 'order', _('Order')
        APPOINTMENT = 'appointment', _('Appointment')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('name'), max_length=150)
    email = models.EmailField(_('email'), blank=True)
    phone = models.CharField(_('phone'), max_length=40, blank=True)
    company = models.CharField(_('company'), max_length=150, blank=True)
    stage = models.CharField(_('stage'), max_length=20, choices=Stage.choices, default=Stage.NEW)
    source = models.CharField(_('source'), max_length=20, choices=Source.choices, default=Source.MANUAL)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('assigned to'),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='crm_contacts',
    )
    tags = models.ManyToManyField(Tag, verbose_name=_('tags'), blank=True, related_name='contacts')
    marketing_consent = models.BooleanField(
        _('agreed to news and offers'),
        default=False,
        help_text=_('Only email marketing to contacts who agreed.'),
    )
    consent_updated_at = models.DateTimeField(_('consent changed'), null=True, blank=True, editable=False)
    consent_source = models.CharField(_('consent given through'), max_length=100, blank=True, editable=False)
    created_at = models.DateTimeField(_('created'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated'), auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('contact')
        verbose_name_plural = _('contacts')
        constraints = [
            # One contact per email address, ignoring case; contacts without email are allowed.
            models.UniqueConstraint(Lower('email'), condition=~Q(email=''), name='crm_contact_email_ci_unique'),
        ]
        indexes = [
            models.Index(fields=['stage', '-created_at'], name='crm_contact_stage_idx'),
            models.Index(fields=['owner'], name='crm_contact_owner_idx'),
        ]

    def __str__(self):
        return self.name or self.email

    def set_consent(self, agreed, source):
        """Record a consent decision with when and how it was given."""
        if agreed != self.marketing_consent or self.consent_updated_at is None:
            self.marketing_consent = agreed
            self.consent_updated_at = timezone.now()
            self.consent_source = source


class Interaction(models.Model):
    """One entry on a contact's timeline: a message, note, call, or an event from another module."""

    class Kind(models.TextChoices):
        FORM = 'form', _('Website message')
        NOTE = 'note', _('Note')
        CALL = 'call', _('Call')
        EMAIL = 'email', _('Email')
        MEETING = 'meeting', _('Meeting')
        SYSTEM = 'system', _('System event')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='interactions', db_index=False)
    kind = models.CharField(_('type'), max_length=20, choices=Kind.choices, default=Kind.NOTE)
    summary = models.CharField(_('summary'), max_length=200)
    body = models.TextField(_('details'), blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('author'),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    occurred_at = models.DateTimeField(_('when'), default=timezone.now)

    class Meta:
        ordering = ['-occurred_at']
        verbose_name = _('timeline entry')
        verbose_name_plural = _('timeline')
        indexes = [models.Index(fields=['contact', '-occurred_at'], name='crm_interaction_contact_idx')]

    def __str__(self):
        return self.summary


class Task(models.Model):
    """A follow-up for staff, such as 'call back on Friday'."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='tasks', verbose_name=_('contact'))
    title = models.CharField(_('task'), max_length=200)
    due_date = models.DateField(_('due'))
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('assigned to'),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='crm_tasks',
    )
    done = models.BooleanField(_('done'), default=False)
    done_at = models.DateTimeField(_('done at'), null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    created_at = models.DateTimeField(_('created'), auto_now_add=True)

    class Meta:
        ordering = ['done', 'due_date']
        verbose_name = _('follow-up task')
        verbose_name_plural = _('follow-up tasks')
        indexes = [models.Index(fields=['done', 'due_date'], name='crm_task_open_due_idx')]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.done and self.done_at is None:
            self.done_at = timezone.now()
        elif not self.done:
            self.done_at = None
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        return not self.done and self.due_date < timezone.localdate()
