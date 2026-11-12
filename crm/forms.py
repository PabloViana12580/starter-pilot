from django import forms
from django.utils.translation import gettext_lazy as _

from core.spam import SpamProtectedForm


class ContactForm(SpamProtectedForm):
    name = forms.CharField(label=_('Your name'), max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    email = forms.EmailField(label=_('Email'), widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    phone = forms.CharField(
        label=_('Phone'),
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'tel', 'inputmode': 'tel'}),
    )
    message = forms.CharField(label=_('How can we help?'), max_length=3000, widget=forms.Textarea(attrs={'rows': 6}))
    marketing_consent = forms.BooleanField(
        label=_('Send me occasional news and offers. I can unsubscribe at any time.'),
        required=False,
    )

    field_order = ['name', 'email', 'phone', 'message', 'marketing_consent', 'website', 'started']
