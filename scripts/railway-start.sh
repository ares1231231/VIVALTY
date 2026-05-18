#!/bin/sh
# Production container entrypoint for Railway.
# Migrations run once at boot; gunicorn starts immediately after so the
# healthcheck can reach /healthz/ without waiting for seed/collectstatic.
set -e

echo "[start] Running migrations..."
python manage.py migrate --noinput

echo "[start] Starting gunicorn on 0.0.0.0:${PORT:-8000} ..."
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${GUNICORN_WORKERS:-2}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
