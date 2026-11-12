from django.urls import path

from . import account_views

urlpatterns = [
    path('login/', account_views.StaffLoginView.as_view(), name='login'),
    # LogoutView only accepts POST, so signing out is CSRF-protected.
    path('logout/', account_views.StaffLogoutView.as_view(), name='logout'),
    path('two-factor/setup/', account_views.mfa_setup, name='mfa_setup'),
    path('two-factor/verify/', account_views.mfa_verify, name='mfa_verify'),
]
