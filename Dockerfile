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

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed && python manage.py collectstatic --noinput && gunicorn config.wsgi:application -b 0.0.0.0:8000 --workers 3 --timeout 120"]
