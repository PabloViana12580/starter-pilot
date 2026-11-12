"""
Business modules installed in this project.

Written by django-starter when the project was created. When you add a module
later, add its app here, its URLs to MODULE_URLS, and set
MODULES_HOLD_PERSONAL_DATA if it stores customers' personal data.
"""

# Django apps of the business modules, in dependency order.
MODULE_APPS = ['pages', 'crm']

# (URL prefix, URLconf module) for each module that serves pages.
MODULE_URLS = [('', 'pages.urls'), ('', 'crm.urls')]

# True when any module stores customers' personal data (names, emails, phone
# numbers...). Turns on two-factor login for staff by default.
MODULES_HOLD_PERSONAL_DATA = True
