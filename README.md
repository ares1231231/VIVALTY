# Vivalty — AI-powered global real estate investment platform

> Connect international investors to high-potential properties across **France, UK, Spain, Switzerland, Italy, UAE and Portugal** — with an AI advisor grounded in our own data.

**One server. One language (Python). One deploy.**

```
vivalty/
├── apps/                Django apps (web, users, geo, properties, ai_advisor, billing)
├── assets/              Tailwind build pipeline (Node, dev-time only)
├── static/css/          Compiled tailwind.css (generated, not committed)
├── config/              Settings, urls, wsgi/asgi
├── manage.py            ← run from here: python manage.py runserver
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 1. Architecture

```
                    ┌────────────────────────────┐
                    │     Browser (any device)   │
                    └──────────────┬─────────────┘
                                   │ HTML + Tailwind + HTMX + tiny JS
                                   ▼
        ┌────────────────────────────────────────────────────┐
        │                Django 5 (one server)               │
        │                                                    │
        │   apps.web    →  Server-rendered website           │
        │   apps.users  →  Auth (email login, roles)         │
        │   apps.geo    →  Country / City                    │
        │   apps.properties → Listings, metrics, favorites   │
        │   apps.ai_advisor →  Chat sessions + streaming     │
        │   apps.billing →  Plans / featured listings        │
        │                                                    │
        │   ─── Service layer (no logic in views) ───        │
        │   apps.properties.services.scoring                 │
        │   apps.ai_advisor.services.{prompts,retriever,advisor}
        │                                                    │
        │   ─── REST API (kept for mobile / partners) ───    │
        │   /api/v1/...   (DRF + JWT)                        │
        └──────┬────────────────────────────┬────────────────┘
               ▼                            ▼
          ┌─────────┐                  ┌────────┐
          │Postgres │ (or sqlite dev)  │ Redis  │ cache + rate limits
          └─────────┘                  └────────┘
                                            │
                                            ▼
                              ┌──────────────────────────┐
                              │ OpenAI Chat Completions  │ streaming
                              └──────────────────────────┘
```

### Why this shape?
- **Single deploy, single language.** One `python manage.py runserver` (or Gunicorn) serves everything: HTML pages, the AI streaming endpoint, the REST API, and the admin panel. Cheap to host (~$5–7/mo on Railway / Render / Fly).
- **Compiled Tailwind + HTMX** — modern look, ~50 KB minified CSS. Node is used **at build-time only**; production is 100% Python.
- **REST API kept on `/api/v1/...`** — so you can ship a mobile app or open a public partner API without rewriting anything.
- **Service-layer architecture.** Views are thin; investment scoring (`apps/properties/services/scoring.py`) and AI orchestration (`apps/ai_advisor/services/*`) are pure functions, easy to test and reuse.
- **Anti-hallucination contract.** The AI advisor only sees platform context + a strict system prompt. Whenever it relies on a country baseline rather than verified city data, every metric carries `is_estimated=true` and the prompt forces the word *estimated* into the answer.
- **Streaming chat.** The chat endpoint streams tokens via Server-Sent Events; the browser consumes the stream incrementally for ChatGPT-style UX (~120 lines of vanilla JS, no React).
- **Indexed search.** Indexes on `(country, city, status)`, `(price)`, `(property_type, status)` plus `metric.investment_score`.

---

## 2. Quick start

Everything lives at the project root — no `cd backend`, no `cd frontend`.

```bash
# 1. Python — from the project root
python -m venv .venv
.\.venv\Scripts\Activate.ps1           # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                  # then edit OPENAI_API_KEY (optional)
python manage.py migrate
python manage.py seed                   # countries, cities, demo properties

# 2. Build the CSS once (Node used at build-time only)
pushd assets
npm install
npm run build                           # → ../static/css/tailwind.css (~50 KB)
popd

# 3. Run the server (front + back, single process)
python manage.py runserver
```

Then open: **http://localhost:8000**

That's it. **One server. One command. Production runs Python only.**

A demo owner is seeded automatically:

```
email:    demo-owner@vivalty.app
password: vivalty-demo-pass
```

To create a Django superuser (admin panel access at `/admin/`):

```bash
python manage.py createsuperuser
```

> If `OPENAI_API_KEY` is not set, the AI advisor returns a deterministic
> structured fallback so the chat UI never breaks during dev/demo.

---

## 3. Quick start (Docker)

```bash
export OPENAI_API_KEY=sk-...     # optional
docker compose up --build
```

Open: **http://localhost:8000** — the same Django process serves the
website, the AI streaming endpoint, the REST API and the admin panel.

The `docker-compose.yml` brings up Postgres + Redis + Django. CSS is
compiled inside the multi-stage `Dockerfile` (Node stage), so production
images contain Python only.

---

## 4. URL map

### Public website (HTML)

| Path | What it shows |
|------|----------------|
| `/` | Landing page + featured listings + covered markets |
| `/marketplace/` | Filterable property grid (HTMX live update on filter submit) |
| `/properties/<id>/` | Detail page + similar + lead form + pinned AI chat |
| `/markets/` | Country baselines + top-scored cities table |
| `/auth/login/` · `/auth/register/` · `/auth/logout/` | Email/password auth |
| `/dashboard/` | Saved properties + (owner) my listings |
| `/owner/new/` | Create a listing (owner role only) |
| `/chat/` · `/chat/<id>/` | Full-screen AI advisor with session sidebar |
| `/htmx/properties/<id>/favorite/` | HTMX: toggle favorite (returns updated button) |
| `/htmx/properties/<id>/lead/` | HTMX: submit lead (returns success card) |
| `/chat/<id>/stream/` | SSE: streams the AI reply token by token |
| `/admin/` | Django admin panel |

### REST API (kept for mobile / partner use)

```
POST   /api/v1/auth/register/                       create account → JWT
POST   /api/v1/auth/token/                          email + password → JWT
POST   /api/v1/auth/token/refresh/                  refresh access
GET    /api/v1/auth/me/                             current user

GET    /api/v1/geo/countries/?search=spain
GET    /api/v1/geo/cities/?country=PT&ordering=-investment_score

GET    /api/v1/properties/                          list + filter + search + ordering
                                                    filters: country, city, type, price_min, price_max,
                                                             score_min, roi_min, tag, is_featured, is_premium
GET    /api/v1/properties/{id}/                     detail
POST   /api/v1/properties/                          owner only
GET    /api/v1/properties/mine/                     owner's listings
POST   /api/v1/properties/{id}/favorite/            toggle favorite
POST   /api/v1/properties/{id}/lead/                send contact lead
GET    /api/v1/properties/{id}/similar/

GET    /api/v1/favorites/
GET    /api/v1/tags/

POST   /api/v1/ai/sessions/                         create chat session
GET    /api/v1/ai/sessions/                         list mine
GET    /api/v1/ai/sessions/{id}/messages/           full history
POST   /api/v1/ai/sessions/{id}/send/               { message } → assistant message
POST   /api/v1/ai/sessions/{id}/stream/             SSE streaming

GET    /api/v1/billing/plans/                       public plan catalog
```

Pagination: PageNumberPagination (default 24 / page).
Throttles: `anon: 120/min`, `user: 600/min`, `ai_chat: 60/min`.

---

## 5. Database schema

| Table                                | Purpose |
|--------------------------------------|---------|
| `users_user`                         | Custom user (email login, role: investor/owner/admin) |
| `geo_country`                        | ISO country + market baselines |
| `geo_city`                           | City avg €/m², yield, demand, trend, risk, score |
| `properties_property`                | Listings (FK country, city, owner) |
| `properties_propertyimage`           | Gallery |
| `properties_investmentmetric`        | 1-1 with Property; computed scores |
| `properties_investmenttag`           | High ROI / Luxury / etc. (M2M) |
| `properties_favorite`                | User → Property |
| `properties_lead`                    | Contact form submissions |
| `ai_advisor_aiconversationsession`   | Chat threads (optionally pinned) |
| `ai_advisor_chatmessage`             | Per-turn messages + RAG context snapshot |
| `billing_plan`, `billing_subscription`, `billing_featuredlistingpurchase` | Monetization (schema-ready) |

---

## 6. AI advisor design

### System prompt (`apps/ai_advisor/services/prompts.py`)
Hard rules: prefer platform data, never invent numbers, surface "estimated"
whenever metrics are derived from baselines, always reply in the
**Quick Answer / Analysis / Comparison / Recommendation** structure.

### Retriever (`apps/ai_advisor/services/retriever.py`)
Lightweight RAG over Postgres:
1. Detect country aliases ("dubai" → AE, "lisbon" → PT) and budget ("100k", "€500,000", "2 million").
2. Pull matching countries + their top-scored cities.
3. Score-rank a top-N of properties (with optional keyword OR over title/description/city).
4. Render a compact context block tagged by kind (`### Countries`, `### Cities`, `### Properties`).

### Generator (`apps/ai_advisor/services/advisor.py`)
- Builds: `system + last 10 turns + user message`.
- Calls OpenAI in stream mode; persists the assembled reply once the generator finishes.
- **Graceful fallback:** if `OPENAI_API_KEY` is missing or the SDK call fails, returns a deterministic structured response.

---

## 7. Investment scoring (`apps/properties/services/scoring.py`)

Pure function, 0–100 score:

| Component          | Weight           | Source                        |
|--------------------|------------------|-------------------------------|
| Yield band         | up to **+40**    | rental_yield × 5              |
| Demand             | +5 / +12 / +20   | low / med / high              |
| Trend              | 0 / +10 / +20    | declining / stable / growth   |
| Risk penalty       | −0 / −8 / −18    | low / med / high              |
| Value-for-money    | +10 / +5 / −8    | implied €/m² vs city avg      |
| Featured bonus     | +5               | sponsored / verified          |

`InvestmentMetric` is refreshed on every `Property.save()` via a Django signal.

---

## 8. Performance, security, ops

- **Indexes** on hot query paths.
- **`select_related` / `prefetch_related`** on every list view to avoid N+1.
- **Redis cache** auto-enables when `REDIS_URL` is set (LocMem fallback for dev).
- **Streaming**: `StreamingHttpResponse` + `X-Accel-Buffering: no` so SSE works behind Nginx.
- **CSRF** on all forms; **session auth** for the website, **JWT** for the API.
- **Throttling** scopes for anon, user, and AI chat separately.
- **Compiled Tailwind CSS** (50 KB minified, fingerprinted in production by
  WhiteNoise's manifest storage) — see CSS pipeline below.

### CSS pipeline (`assets/`)

| Command | Effect |
|---------|--------|
| `cd assets && npm install` | One-time install of Tailwind (no other deps). |
| `npm run build` | Build minified `../static/css/tailwind.css`. Run before deploying or after editing templates. |
| `npm run watch` | Rebuild on save during development. |

Where things live:

```
assets/
├── package.json              # only dependency: tailwindcss
├── tailwind.config.js        # content scan + brand colors + safelist
└── src/input.css             # @tailwind directives + @layer components

static/css/
└── tailwind.css              # generated; gitignored
```

The Tailwind config scans `apps/**/templates/**/*.html` plus the Python files
that emit class strings (`templatetags/*.py`, `forms.py`) and includes a
safelist for dynamically-built tag colors (`bg-{{ tag.color }}-50`, etc.).

### Production deploy checklist

```bash
pip install -r requirements.txt
pushd assets && npm ci && npm run build && popd
python manage.py migrate --noinput
python manage.py collectstatic --noinput      # WhiteNoise hashes & gzips
gunicorn config.wsgi --workers 3 --bind 0.0.0.0:8000
```

Production has zero Node/JS runtime requirement — only at build time.

---

## 9. Roadmap

- pgvector retriever for semantic property search (drop-in for `retriever.py`).
- Stripe webhook for `billing.Subscription` + `FeaturedListingPurchase`.
- Background metric recompute via Celery + Redis when external market data is ingested.
- Admin moderation queue (status `pending` → review → `active`).
- i18n (EN / FR / ES / IT / PT / AR).
- Replace seed data with real listings: either let owners upload, or wire in
  a paid market data API per country (Idealista, PropertyData.co.uk, ATTOM, etc.).
