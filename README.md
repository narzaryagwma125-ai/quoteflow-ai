# QuoteFlow AI

A secure, mobile-first SaaS platform for cleaning businesses to create, send, track, and get paid for quotes. QuoteFlow AI pairs a FastAPI backend with a Next.js/TypeScript/Tailwind frontend and includes AI-assisted quote writing, Stripe subscriptions, secure customer-facing quote links, and a usage-based free tier.

## Features

- **Quotes** — create, edit, send, duplicate coverage via re-send, revoke public links, generate branded PDFs, and auto-numbering (e.g. `Q-2026-0001`).
- **Public quote links** — shareable, expiring, revocable links where customers view a quote and accept or reject it (CSRF-protected).
- **AI assistant** — generated service descriptions, polished rewrites, quote introductions, and follow-up messages (Gemini). Keys never leave the backend; usage is metered.
- **Customers** — CRM with per-customer quote history and totals.
- **Billing** — Stripe Checkout subscriptions, webhook-driven plan changes, cancellations, and monthly usage meters.
- **Plans** — Free: 3 quotes/mo, 10 AI assists, 25 customers. Starter ($9/mo): 50 quotes, 50 AI. Business ($19/mo): unlimited quotes, 200 AI, advanced dashboard. New accounts get a 5-day free trial with Starter-level limits.
- **Security** — Argon2id password hashing, server-side sessions stored only as hashes, double-submit-cookie CSRF, origin verification, rate limiting, security headers, and no raw secrets in logs.

## Repository layout

```
backend/    FastAPI application (API, services, models, tests)
frontend/   Next.js 14 application (App Router, Tailwind, Vitest)
docker-compose.yml   Postgres + backend + frontend
Makefile    Common dev commands
```

## Prerequisites

- Docker + Docker Compose (recommended) **or** Python 3.12+ / Node.js 20+ installed locally
- Optional: a Gemini API key (AI features degrade gracefully when unset)
- Optional: Stripe test-mode keys (billing endpoints return a clear error when unset)

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env       # then edit secrets (dev defaults are fine)
make up                                      # builds and starts db + backend + frontend
make migrate                                 # apply schema
make seed                                    # optional dev seed data
```

- Frontend: http://localhost:3000
- API + Swagger docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/api/health

Stop everything with `make down`. Watch logs with `make logs`.

## Local development (no Docker)

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
# point DATABASE_URL at any PostgreSQL (or use SQLite for quick tests):
#   DATABASE_URL=sqlite+aiosqlite:///./dev.db
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                        # http://localhost:3000
```

In dev and production, the frontend proxies `/api/*` to the backend via `next.config.mjs`. This keeps the session cookie first-party to the frontend origin.

## Configuration

All settings are environment variables (see `backend/.env.example` and `frontend/.env.example`). Important ones:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | At least 32 chars. Required in production. |
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://...`). |
| `FRONTEND_URL` | Allowed origin + base for public links (CSRF origin allowlist). |
| `GEMINI_API_KEY` | AI provider key. |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_STARTER_PRICE_ID`, `STRIPE_BUSINESS_PRICE_ID` | Billing + subscription activation. |
| `UPLOAD_DIR` | Where uploaded logos are stored on disk. |

Production startup fails fast if required secrets are missing or placeholder values. `SESSION_COOKIE_SECURE` is forced on when `APP_ENV=production`.

## Running tests

```bash
make test            # backend + frontend (in Docker)
make test-backend    # backend only
make test-frontend   # frontend only
```

Backend tests use an isolated SQLite database and apply the schema programmatically (no Postgres required). Frontend tests use Vitest + React Testing Library.

## Commands reference

```bash
make build        # build images
make migrate      # run alembic migrations
make seed         # dev seed data
make lint         # ruff + eslint
make dev-backend  # run API locally
make dev-frontend # run frontend locally
```

## Public quote link flow

1. From a quote page, **Send** or **Copy link** issues a high-entropy token; only its SHA-256 hash is stored.
2. The customer opens `{FRONTEND_URL}/q/{token}`, sees the branded quote (no auth), and can accept or reject with their name/email.
3. Accept/reject is CSRF-protected via a double-submit cookie set when the page loads.
4. Link statuses drive the dashboard pipeline: `draft → sent → viewed → accepted/rejected`, with expiry and owner revocation.

## Env: AI and billing degradation

- Without `GEMINI_API_KEY`, AI endpoints return 503 with a helpful message; quote creation/editing still works.
- Without Stripe keys, `/api/billing/checkout` returns a clear 400; free-tier usage is unaffected.

## Security

See [SECURITY.md](./SECURITY.md) for threat model, controls, and reporting.

## Privacy & terms

- [PRIVACY.md](./PRIVACY.md) — what data we collect, why, and how it's handled.
- [TERMS.md](./TERMS.md) — acceptable use and liability terms.

## Roadmap / status

- Backend, frontend, and test suites are written end-to-end. Verify with `make test` in a working shell before deploying.
- Reminders worker (`backend/app/scripts/reminders_worker.py`) exists for automated quote follow-ups; wire it into a scheduler when productionized.