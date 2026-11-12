"""Gunicorn settings, read from the environment so any hosting platform can run it."""

import os

bind = f'0.0.0.0:{os.environ.get("PORT", "8000")}'
# One process keeps the in-memory rate limits accurate; threads add concurrency.
workers = int(os.environ.get('WEB_CONCURRENCY', '1'))
threads = int(os.environ.get('GUNICORN_THREADS', '4'))
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '60'))
accesslog = '-'
errorlog = '-'
forwarded_allow_ips = os.environ.get('FORWARDED_ALLOW_IPS', '*')
