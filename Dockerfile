# Container image for hosts that run containers (Fly.io, Cloud Run, Azure Container Apps, Koyeb...).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --require-hashes -r requirements.txt

COPY . .
# collectstatic needs settings to import; these values exist only during the build.
RUN DJANGO_SECRET_KEY=build-only DATABASE_URL=postgresql://build:build@localhost/build \
    python manage.py collectstatic --noinput

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]
