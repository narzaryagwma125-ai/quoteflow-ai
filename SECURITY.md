# Security

This document describes the threat model, security controls, and how to report a vulnerability for QuoteFlow AI.

## Scope

- FastAPI backend (`backend/`)
- Next.js frontend (`frontend/`)
- Docker deployment in `docker-compose.yml`
- Data returned by the public quote-link feature

## Secrets handling

- **Never commit secrets.** `.env` files are git-ignored; template `.env.example` files contain placeholders only.
- `SECRET_KEY`, Gemini, and Razorpay values are read from the environment at boot.
- Production startup **fails fast** (`app/core/config.py:validate_production`) if required secrets are missing or placeholder values.
- The database URL is redacted before logging (`settings.sanitized_database_url`).

## Authentication & sessions

- Passwords are hashed with **Argon2id** (`app/security/password.py`).
- Sessions are opaque, high-entropy random tokens stored only as **SHA-256 hashes** in `user_sessions`; the client holds the raw token in an **HttpOnly** cookie.
- Sessions expire server-side and can be revoked (logout, password change, account deletion revokes all).
- Login/signup/reset are rate limited by client IP.

## Token handling

- Email verification, password reset, and public-quote tokens are single-use, time-limited, and stored **only as hashes**.
- Public quote links can be revoked by the owner and expire (default 30 days).
- Raw tokens are returned to the browser **once** (send / copy-link); re-copying a link issues a fresh token.

## CSRF / cross-origin protections

- State-changing API routes call `verify_origin()` (in `app/api/deps.py`), which rejects requests whose `Origin` is not the configured frontend origin or the current host. Cookies are `SameSite=Lax`.
- The public accept/reject actions use the **double-submit cookie** pattern (`app/security/csrf.py`): a `quoteflow_csrf` cookie is set when the public page loads, and the same value must be echoed in the `X-CSRF-Token` header.

## Input validation & injection

- All request bodies are validated by Pydantic schemas (length, type, range).
- Quote math is re-derived server-side in `app/services/quote_calc.py`; totals submitted by clients are never trusted.
- Rate limits: brute-force endpoints (login, signup, password recoveries) and abuse-prone endpoints (AI, PDF generation, logo upload, public links) are throttled per client IP.

## Payments

- Card numbers, CVV, and bank details are **never collected or stored** by this app. Payment happens on Razorpay's hosted Checkout page.
- Price IDs come from environment config, never from the client.
- Subscriptions are activated/updated only via **signature-verified webhooks**, and events are processed exactly once (unique `(provider, provider_event_id)` in `payment_events`).

## AI

- The Gemini API key stays on the backend; prompts never contain passwords or payment data.
- Customer names/emails are sent upstream only when the user explicitly requests a task that needs them (e.g. a follow-up message).

## Logging & data minimization

- Logs never include request bodies, passwords, or raw tokens.
- Audit log (`app/models/audit_log.py`) records only action names, entity ids, and a short IP hash prefix.

## Headers & transport

- Security headers (HSTS, frame denial, nosniff, referrer policy, content-type sniffing defenses) are set in `backend/app/core/headers.py` and mirrored in `frontend/next.config.mjs`.
- Session cookies are `Secure` in production and samesite-policy-protected.

## Threat model summary

| Threat | Mitigation |
| --- | --- |
| Account takeover via password hash theft | Argon2id; hashes only; no raw secrets on disk |
| Session hijacking / fixation | HttpOnly, Secure, SameSite cookies; server-side validation; revocation on logout/password change |
| CSRF on account/quote actions | Origin verification + SameSite cookies |
| CSRF on public accept/reject | Double-submit cookie |
| Brute force / credential stuffing | Per-IP rate limiting on login/signup |
| Public-link abuse | High-entropy tokens, expiry, owner revocation, no-index headers |
| Tampered totals/costs | Server-side recalculation of all money |
| Webhook replay/forgery | Razorpay signature verification + idempotent event processing |
| Secret leakage into logs | Redacted config logging; no request-body logging |

## Responsible disclosure

Do **not** open a public issue for security problems. Contact the maintainers privately with:

- The affected component and version.
- A minimal reproduction.
- Impact description.

We acknowledge reports and provide an assessment. Please give reasonable time before any public disclosure.

## Hardening checklist before production

- [ ] Replace `SECRET_KEY` with a long random value (≥32 chars).
- [ ] Set `APP_ENV=production` (forces `Secure` cookies + startup validation).
- [ ] Configure real SMTP, Gemini, and Razorpay credentials.
- [ ] Run the backend behind TLS and set `FRONTEND_URL` to the public origin.
- [ ] Run `make test` and confirm all tests pass.
- [ ] Keep dependency upgrades current (see `pyproject.toml` / `package.json`).