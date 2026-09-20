# QuoteFlow AI audit and fixes

Audited the uploaded project across backend API, database/session handling, frontend integration, billing webhooks, security-sensitive input handling, Docker health checks, and documentation.

## Fixes applied

1. **Neon/asyncpg database connection**
   - Translates `sslmode=require` to asyncpg's `ssl=require`.
   - Removes unsupported `channel_binding` from the asyncpg connection URL.
   - Keeps normal PostgreSQL/SQLite URLs unchanged.
   - This fixes the Render 500 caused by `asyncpg.connect()` receiving unsupported `sslmode` / `channel_binding` keyword arguments.

2. **Backend health endpoint**
   - Health is now exposed at `/api/health`, matching the Docker health checks, frontend proxy, README, and tests.

3. **Production root endpoint**
   - Production no longer advertises `/api/docs` when Swagger is intentionally disabled.

4. **Stripe webhook ordering**
   - Subscription events can recover/create the local subscription from Stripe subscription metadata if they arrive before `checkout.session.completed`.

5. **Contact email HTML escaping**
   - User-controlled contact fields are escaped before being inserted into the HTML email body.

6. **Example secret cleanup**
   - Removed the hard-coded secret-looking value from `backend/.env.example` and replaced it with a placeholder.

7. **Documentation**
   - Corrected the local Swagger URL to `/api/docs`.
   - Corrected the frontend/backend proxy description.

8. **Regression tests**
   - Added tests for Neon/asyncpg URL normalization.
   - Added a Stripe out-of-order subscription webhook regression test.

## Validation performed

- Python source compilation: passed for all Python files after the fixes.
- Database URL normalization logic: passed for `sslmode=require`, `channel_binding=require`, existing `ssl=require`, and SQLite URL cases.
- Quote calculation smoke test: passed.
- Frontend TypeScript check (`tsc --noEmit`): passed.
- Frontend ESLint: passed.

The complete backend test suite could not be executed in this isolated environment because the uploaded project does not include a usable Linux `aiosqlite`/`asyncpg` installation and network access is unavailable for installing them. The frontend Vitest bundle was also Windows-installed and lacked its Linux Rollup optional dependency. These are environment limitations, not test failures in the source.

## Important security note

The uploaded ZIP contained a real `backend/.env` and a secret-looking value in the original `backend/.env.example`. The clean fixed package excludes the real `.env`.

Because credentials were included in the uploaded ZIP, **rotate the SMTP password, Gemini API key, Stripe secret/webhook secret, database password/connection credentials, and any other credentials that were real** before using the application again. Do not commit or upload the real `.env`.

## Email verification / Render SMTP fix (2026-09-19)

- Replaced production SMTP delivery with Resend's HTTPS Email API in `backend/app/services/email.py`.
- This avoids direct SMTP connections to ports 25/465/587, which can be blocked on managed/free hosting.
- Added `RESEND_API_KEY`, `RESEND_API_URL`, and `EMAIL_API_TIMEOUT_SECONDS` settings.
- `EMAIL_VERIFICATION_REQUIRED` defaults to `true` in the backend configuration and `.env.example`.
- Production startup validates `RESEND_API_KEY` and `EMAIL_FROM` when email verification is enabled.
- `EMAIL_FROM` must be a sender/domain verified in Resend.
- Existing email verification token generation and `/api/auth/verify-email` flow are preserved.

### Render environment variables

Set these in the Render backend service:

```text
EMAIL_VERIFICATION_REQUIRED=true
RESEND_API_KEY=<your Resend API key>
RESEND_API_URL=https://api.resend.com/emails
EMAIL_API_TIMEOUT_SECONDS=20
EMAIL_FROM=<sender on a verified Resend domain>
```

Do not put the Resend API key in source code or commit it to Git.

## Subscription countdown and billing dates

- Billing now shows the Stripe-backed next billing date from `current_period_end`.
- An updating days/hours/minutes/seconds countdown is shown for active subscriptions.
- If cancellation is scheduled, the same countdown is shown as paid-access end time instead of a renewal.
- Free-trial banners now show a live countdown to `trial_expires_at`.
- Trial and subscription dates are calculated in the browser from server-provided timestamps; the server remains the source of truth for entitlement enforcement.
- The billing page displays the customer-facing `Basic` label for the internal `starter` plan.

## Built-in professional quotation templates
- Added five selectable built-in PDF quotation designs: Classic, Modern, Minimal, Executive, and Creative.
- Added persistent `template_type` values and Alembic migration `0004_builtin_quote_templates`.
- Existing `default` and `custom_docx` behavior remains backward compatible.
- Added authenticated `/api/business-profile/template/style/{style}` endpoint.
- Business page now shows five template previews and a Save settings action.
- All built-in templates keep the same quote calculations, business data, logo, line items, taxes, totals, notes, terms, and signature data.
- Custom DOCX templates remain available and take precedence when selected.
