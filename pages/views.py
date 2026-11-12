from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def home(request):
    return render(request, 'pages/home.html')


@require_GET
def about(request):
    return render(request, 'pages/about.html')


@require_GET
def privacy(request):
    return render(request, 'pages/privacy.html')


@require_GET
def terms(request):
    return render(request, 'pages/terms.html')
