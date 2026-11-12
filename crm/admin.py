import logging

from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from .exports import contact_data_response, contacts_csv_response
from .models import Contact, Interaction, Tag, Task

security_log = logging.getLogger('security')


class InteractionInline(admin.StackedInline):
    model = Interaction
    extra = 1
    fields = ('kind', 'summary', 'body', 'occurred_at', 'author')
    readonly_fields = ('author',)
    ordering = ('-occurred_at',)


class TaskInline(admin.TabularInline):
    model = Task
    extra = 1
    fields = ('title', 'due_date', 'assigned_to', 'done')
    ordering = ('done', 'due_date')


def _stage_action(stage):
    def action(modeladmin, request, queryset):
        updated = queryset.update(stage=stage, updated_at=timezone.now())
        modeladmin.message_user(
            request,
            ngettext(
                '%(count)d contact moved to %(stage)s.',
                '%(count)d contacts moved to %(stage)s.',
                updated,
            )
            % {'count': updated, 'stage': Contact.Stage(stage).label},
        )

    action.__name__ = f'move_to_{stage}'
    action.short_description = _('Move to stage: %(stage)s') % {'stage': Contact.Stage(stage).label}
    action.allowed_permissions = ('change',)
    return action


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'stage', 'owner', 'open_tasks', 'marketing_consent', 'created_at')
    list_filter = ('stage', 'source', 'owner', 'tags', 'marketing_consent')
    show_facets = admin.ShowFacets.ALWAYS  # counts per stage: the lead pipeline at a glance
    search_fields = ('name', 'email', 'phone', 'company')
    list_select_related = ('owner',)
    autocomplete_fields = ('tags',)
    readonly_fields = ('source', 'consent_updated_at', 'consent_source', 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'email', 'phone', 'company')}),
        (_('Pipeline'), {'fields': ('stage', 'owner', 'tags', 'source')}),
        (_('Consent'), {'fields': ('marketing_consent', 'consent_updated_at', 'consent_source')}),
        (_('Record'), {'fields': ('created_at', 'updated_at')}),
    )
    inlines = (InteractionInline, TaskInline)
    actions = [
        *[_stage_action(stage) for stage in Contact.Stage.values],
        'export_csv',
        'export_personal_data',
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _open_tasks=Count('tasks', filter=Q(tasks__done=False)),
            )
        )

    @admin.display(description=_('open tasks'), ordering='_open_tasks')
    def open_tasks(self, contact):
        return contact._open_tasks

    def save_model(self, request, obj, form, change):
        if 'marketing_consent' in form.changed_data:
            obj.set_consent(obj.marketing_consent, f'Staff ({request.user.get_username()})')
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        for instance in formset.save(commit=False):
            if isinstance(instance, Interaction) and instance.author_id is None:
                instance.author = request.user
            if isinstance(instance, Task) and instance.created_by_id is None:
                instance.created_by = request.user
            instance.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()

    @admin.action(description=_('Export selected contacts to CSV'), permissions=['view'])
    def export_csv(self, request, queryset):
        security_log.info('crm.export_csv user_id=%s count=%s', request.user.pk, queryset.count())
        return contacts_csv_response(queryset)

    @admin.action(description=_("Download one contact's personal data (privacy request)"), permissions=['view'])
    def export_personal_data(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, _('Select exactly one contact.'), messages.WARNING)
            return None
        contact = queryset.get()
        security_log.info('crm.export_personal_data user_id=%s contact=%s', request.user.pk, contact.pk)
        return contact_data_response(contact)


class DueFilter(admin.SimpleListFilter):
    title = _('due')
    parameter_name = 'due'

    def lookups(self, request, model_admin):
        return (('overdue', _('Overdue')), ('today', _('Today')), ('upcoming', _('Upcoming')))

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == 'overdue':
            return queryset.filter(done=False, due_date__lt=today)
        if self.value() == 'today':
            return queryset.filter(done=False, due_date=today)
        if self.value() == 'upcoming':
            return queryset.filter(done=False, due_date__gt=today)
        return queryset


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'contact', 'due_date', 'overdue', 'assigned_to', 'done')
    list_editable = ('done',)
    list_filter = (DueFilter, 'done', 'assigned_to')
    search_fields = ('title', 'contact__name', 'contact__email')
    list_select_related = ('contact', 'assigned_to')
    autocomplete_fields = ('contact',)
    actions = ['mark_done']

    @admin.display(boolean=True, description=_('overdue'))
    def overdue(self, task):
        return task.is_overdue

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description=_('Mark selected tasks as done'), permissions=['change'])
    def mark_done(self, request, queryset):
        for task in queryset.filter(done=False):
            task.done = True
            task.save(update_fields=['done', 'done_at'])


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ('name',)
