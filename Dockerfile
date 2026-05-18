# --- Stage 1: build the CSS bundle (Node only at build-time) ---
FROM node:20-alpine AS css
WORKDIR /css
COPY assets/package.json assets/tailwind.config.js ./
RUN npm install --no-audit --no-fund
COPY assets/src ./src
COPY apps ./scan/apps
# tailwind.config.js looks at ../apps/** — relative to /css.
# We mirror that layout so the same config works inside the container.
RUN sed -i 's|../apps|scan/apps|g' tailwind.config.js \
 && npx tailwindcss -i ./src/input.css -o /tailwind.css --minify

# --- Stage 2: Python runtime ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=css /tailwind.css /app/static/css/tailwind.css

# Collect static assets at image build time (not on every container boot).
ENV DJANGO_SECRET_KEY=build-collectstatic-only \
    DJANGO_DEBUG=0 \
    DJANGO_ALLOWED_HOSTS=localhost
RUN python manage.py collectstatic --noinput

RUN chmod +x /app/scripts/railway-start.sh

EXPOSE 8000

CMD ["/app/scripts/railway-start.sh"]
