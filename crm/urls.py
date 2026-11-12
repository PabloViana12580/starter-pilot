from django.urls import path

from . import views

app_name = 'crm'

urlpatterns = [
    path('contact/', views.contact, name='contact'),
    path('contact/thanks/', views.contact_thanks, name='contact_thanks'),
]
