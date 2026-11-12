from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from core.spam import log_spam, rate_limited

from .forms import ContactForm
from .services import submit_inquiry


@require_http_methods(['GET', 'POST'])
def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST':
        if rate_limited(request, 'crm-contact', limit=settings.CRM_CONTACT_RATE_LIMIT, window=3600):
            log_spam(request, 'contact', 'rate_limit')
            return render(request, 'crm/contact.html', {'form': form, 'rate_limited': True}, status=429)
        if form.is_valid():
            reason = form.spam_reason()
            if reason:
                # Look the same as success, so bots learn nothing; nothing is saved.
                log_spam(request, 'contact', reason)
            else:
                data = form.cleaned_data
                submit_inquiry(
                    name=data['name'],
                    email=data['email'],
                    phone=data['phone'],
                    message=data['message'],
                    marketing_consent=data['marketing_consent'],
                )
            return redirect('crm:contact_thanks')
    return render(request, 'crm/contact.html', {'form': form})


@require_GET
def contact_thanks(request):
    return render(request, 'crm/contact_thanks.html')
