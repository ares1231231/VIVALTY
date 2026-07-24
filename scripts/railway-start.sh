#!/bin/sh
# Production container entrypoint for Railway.
# Migrations run once at boot; gunicorn starts immediately after so the
# healthcheck can reach /healthz/ without waiting for seed/collectstatic.
set -e

echo "[start] Running migrations..."
python manage.py migrate --noinput

# Idempotent (upserts by listing_ref) and self-sufficient (creates missing
# countries/cities/tags), so it is safe on every boot. Non-fatal: a bad
# curated file must never block the deploy.
echo "[start] Importing curated listings..."
python manage.py import_curated_listings || echo "[start] Curated import failed (non-fatal), continuing."

# Unfeature listings whose paid boosts lapsed (editorial features untouched).
echo "[start] Expiring lapsed featured boosts..."
python manage.py expire_featured || echo "[start] Boost expiry failed (non-fatal), continuing."

# Renewal reminders for boosts expiring within 2 days (idempotent via DB flag).
echo "[start] Sending boost-expiry reminders..."
python manage.py notify_expiring_boosts || echo "[start] Boost reminders failed (non-fatal), continuing."

echo "[start] Starting gunicorn on 0.0.0.0:${PORT:-8000} ..."
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${GUNICORN_WORKERS:-2}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
