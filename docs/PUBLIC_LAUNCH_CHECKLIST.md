# AURORA - Remaining Work Before Public Launch

**Context:** AURORA is a FastAPI + PostgreSQL/PostGIS + Redis/RQ backend
(`backend/`) and a React/Vite frontend (`aurora-frontend/`). This checklist
must be reviewed against the current `main` branch before implementation.

The work below should be delivered as separate pull requests rather than one
giant change. Each item needs an owner, acceptance criteria, rollback plan, and
evidence from a real environment.

## Before touching anything

1. Clone the current repository from GitHub:

   ```bash
   git clone https://github.com/sybertoooth7-lgtm/AURORA.git
   ```

   If Git is unavailable, use:

   ```text
   https://codeload.github.com/sybertoooth7-lgtm/AURORA/tar.gz/refs/heads/main
   ```

2. Inspect the actual `main` branch. Do not assume this checklist is still
   accurate.
3. Verify every filename character-for-character, including capitalization and
   spaces. Prefer complete paste-ready files over web-editor patches.
4. Test in a real sandbox: install dependencies, run the test suite, run
   Alembic against PostgreSQL/PostGIS, and report exact errors.

## 1. Deploy it - highest priority

Nothing else matters if the product is not live and observable.

### Backend platform

Use Railway or Render for the backend, worker, PostgreSQL/PostGIS, and Redis.
Do not use Vercel for the long-running API or RQ worker.

- Create PostgreSQL with PostGIS enabled and verify:
  `CREATE EXTENSION postgis;`.
- Create Redis.
- Deploy `backend/` as the API service using the Dockerfile command:
  `alembic upgrade head && uvicorn main:app ...`.
- Deploy a second service from the same image with:
  `python worker.py`. The worker must run continuously or analyses remain
  `pending`.
- Configure `DATABASE_URL`, `REDIS_URL`, a real random `SECRET_KEY`,
  `ENVIRONMENT=production`, `CORS_ORIGINS`, and `FRONTEND_URL`.
- Configure all remaining variables from `backend/.env.example`.
- Enable structured logs, health checks, alerts, and a rollback image.

Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Frontend platform

Deploy `aurora-frontend/` to Vercel or Netlify as a Vite build. Set
`VITE_API_BASE_URL` to the deployed backend URL and configure the production
frontend URL in backend CORS and reset-link settings.

### Live acceptance test

Against the real URLs:

1. Register a real account.
2. Submit an area of interest.
3. Confirm the worker processes it and results appear.
4. Request a password reset and verify the email and link.
5. Verify CORS, browser-console, API, worker, database, and Redis logs.
6. Confirm the health and readiness endpoints and alerting behavior.

## 2. Configure real Sentinel Hub credentials

Without Copernicus credentials, analyses use `DemoSatelliteProvider` and
produce deterministic simulated data.

1. Create an account at <https://dataspace.copernicus.eu/>.
2. Create an OAuth client at
   <https://shapps.dataspace.copernicus.eu/dashboard/>.
3. Set `SENTINEL_CLIENT_ID` and `SENTINEL_CLIENT_SECRET` in the deployment.
4. Submit a real area with recent Sentinel-2 coverage.
5. Confirm `metadata_json` reports `"source": "sentinel-2-l2a"` rather than
   `"source": "demo"`.
6. Review whether NDVI is plausible for the selected land cover and record the
   evidence in the deployment runbook.

Never present simulated results as real observations.

## 3. Configure SMTP for password-reset email

`app/email.py` must send mail in production rather than only logging a reset
link. Choose an SMTP provider such as Gmail, SendGrid, Mailgun, Postmark, or
AWS SES and configure:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`

Request a reset against the live deployment, confirm delivery, verify the
single-use and expiry behavior, and ensure secrets never appear in logs.

## 4. Verify distributed rate limiting

The general API budget and stricter authentication budget must be shared across
API replicas. Use Redis with an atomic sliding-window or token-bucket design
keyed by the client identity and endpoint class, preserving the stricter
budgets for `/auth/token` and `/auth/register`.

Acceptance criteria:

- Two API replicas share counters.
- Expired counters are removed automatically.
- Login lockout remains correct at scale.
- `429` responses include useful retry information.
- Redis outage behavior is explicit and monitored.
- Tests cover concurrency, expiry, replica sharing, and trusted-proxy/IP
  handling.

## 5. Add a minimal admin surface

`User.is_admin` and `require_admin` should gate a minimal operational API:

- `GET /admin/users`
- `POST /admin/users/{id}/disable`
- `POST /admin/users/{id}/enable`
- Audit access and account-state changes.

Keep the first version API-only; a database console is sufficient for the
current scale if it is access-controlled and audited. Add pagination,
non-enumerable errors, authorization tests, and protection against an admin
disabling the last active administrator.

## 6. Publish legal basics

Add short Privacy Policy and Terms of Service pages to the frontend before
accepting real users. Have qualified counsel review them, especially against
Kenya's Data Protection Act 2019 and the laws of the countries where AURORA
operates. This checklist is not legal advice and must not substitute for
jurisdiction-specific review.

Cover data collection, lawful basis, retention, subprocessors, cookies,
security incidents, user rights, acceptable use, service limitations, imagery
rights, simulated versus real data, and dispute/contact information.

## 7. Confirm managed-service backups

This is an operational control, not a code change:

- Enable automatic PostgreSQL backups and point-in-time recovery where
  available.
- Confirm retention, encryption, access control, and backup-region policy.
- Perform a restore drill against a non-production database.
- Document RPO/RTO and the person responsible for recovery.
- Verify Redis persistence or explicitly document which data is disposable.

Do not onboard real customer data until a restore has been demonstrated.

## Recommended execution order

1. Deploy API, worker, PostGIS, Redis, and frontend.
2. Configure and validate real Sentinel Hub data.
3. Configure and validate SMTP password resets.
4. Verify distributed rate limiting under multiple replicas.
5. Add and test the admin API.
6. Publish counsel-reviewed legal pages.
7. Enable and test managed-service backups.

Each item should be a separate PR with a production runbook and evidence. The
public-launch gate is passed only when deployment, real data provenance,
password reset, distributed abuse controls, admin operations, legal pages, and
recovery procedures have all been verified.
