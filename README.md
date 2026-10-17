# Hisaab Portal: construction-material supply

A web portal that replaces the paper registers of a small construction-material supplier (sand, cement,
blocks, gravel, crush; 5 tractor-trolleys, 1 dumper, 3 loaders). Customer khata, supplier payments, yard stock,
diesel, rentals, labour wages and advances all live in one place, so balances, outstanding and profit always agree.

The design is in [`ARCHITECTURE.md`](ARCHITECTURE.md). This repo implements it.

```
backend/    FastAPI + SQLAlchemy 2 + Alembic (PostgreSQL 17)      → API, posting engine, reports, PDF/Excel
frontend/   React 18 + Vite + TypeScript + Ant Design 5            → the portal UI
deploy/     Caddyfile, backup container (pg_dump, retention, off-site, restore test)
docker-compose.yml          production stack (caddy + api + db + backup)
docker-compose.staging.yml  staging override (own DB / volumes / port)
.github/workflows/ci.yml    lint + tests + image build + SSH deploy
```

## The one idea that matters: hidden double-entry

The accountant fills simple forms (challan, payment, diesel). Behind each form the **posting engine**
(`backend/app/accounting/posting.py`, the only writer of journals) writes a *balanced* journal entry in the **same
DB transaction** as the document. So the books cannot go out of balance, and every report is a query on
`journal_lines`. Event → Dr/Cr mappings live in one file, `accounting/rules.py`.

* No hard delete of financial documents: **void** with a reason posts a reversal; **edit** = reverse + re-post.
* **Month lock**: nothing dated in a locked month can be added, edited or voided.
* **Stock** uses a moving weighted average; each challan posts COGS at the average, so margin is exact.
  The Inventory ledger always equals the yard-stock value (there is a test for it).
* Money is `NUMERIC(14,2)` / Python `Decimal` / decimal *strings* in JSON. Never a float.

## Run it locally

Prerequisites: Python 3.12, Node 18+ (20 recommended), and either Docker (for PostgreSQL) or nothing (SQLite demo).

```bash
# 1. database: PostgreSQL 17 in Docker ...
docker compose -f docker-compose.dev.yml up -d

# 2. backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head          # create the schema
python -m app.seed            # demo data: 45 days of realistic activity (or `python -m app.bootstrap` for an empty start)
uvicorn app.main:app --reload # http://127.0.0.1:8000/api/docs

# 3. frontend (another terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173  (proxies /api to 127.0.0.1:8000)
```

**No Docker?** Use SQLite for a quick look: in `backend/.env` set `DATABASE_URL=sqlite:///./dev.db` and
`AUTO_CREATE_TABLES=true`, then `python -m app.seed --reset`. (Production must use PostgreSQL.)

Demo logins (created by the seed): **admin / admin12345** (owner) and **munshi / munshi12345** (accountant).
`python -m app.bootstrap` alone creates just the first admin from `BOOTSTRAP_ADMIN_*`: change that password.

## Tests and checks

```bash
cd backend && source .venv/bin/activate
ruff check . && ruff format --check .
pytest -q                                   # 51 tests on SQLite (fast)
TEST_DATABASE_URL=postgresql+psycopg://hisaab:hisaab@localhost:5432/hisaab_test pytest -q   # same tests on PostgreSQL

cd frontend
npm run typecheck && npm run lint && npm test && npm run build
npx playwright install chromium             # once
npx playwright test                         # browser smoke tests; needs the API (seeded) + `npm run dev` running
```

The backend tests cover: every posting rule, weighted-average cost, void/edit/reversal, month lock, idempotency
(`client_ref`), period-aware aging, all reports and their Excel/PDF exports, auth (rate limit, refresh rotation and
reuse detection), role permissions, the audit trail, and *invariants* (trial balance balances, every entry balances,
inventory = stock value, reversals mirror originals) including a full 45-day seeded scenario.

## What is where

| Architecture module | Backend | Frontend |
|---|---|---|
| auth, users, roles | `modules/auth`, `core/permissions.py` | `features/auth`, `features/admin/UsersPage` |
| masters, rate cards | `modules/masters` | `features/masters` |
| purchases, stock | `modules/purchases`, `modules/stock` | `features/purchases`, `features/stock` |
| deliveries (challan) | `modules/deliveries` | `features/deliveries` (keyboard-first entry) |
| rentals | `modules/rentals` | `features/rentals` |
| invoices | `modules/invoices` | `features/invoices` |
| payments, expenses | `modules/payments`, `modules/expenses` | `features/payments`, `features/expenses` |
| labour | `modules/labour` | `features/labour` (attendance grid, settlements) |
| accounting | `accounting/` (chart, posting, rules, locks, opening) | `features/admin/{OpeningPage,LocksPage}` |
| reports | `modules/reports` (queries, Excel, PDF, documents) | `features/reports` |
| audit | `audit/` (session hooks → `audit_logs`) | `features/admin/AuditPage` |

API: `/api/v1/...`, OpenAPI at `/api/docs` (admin-only with `?token=` when `ENV=prod`). Errors are always
`{ "code", "message", "details" }`. Lists take `?page=&size=&from=&to=&q=&sort=`. Voids are
`POST /<doc>/{id}/void {reason}`; there is no `DELETE` on financial documents.

### Roles

| | Admin | Accountant |
|---|---|---|
| Daily entries (challan, purchase, payment, diesel, rental, attendance, settlement) | ✅ | ✅ |
| Edit entries | ✅ | ✅ |
| **Void**, reports with profit (vehicle P&L, margin, P&L, outstanding, labour cost, rental income) | ✅ | ❌ |
| Users, opening balances, month lock, audit log, trial balance | ✅ | ❌ |

Permissions are checked on **every endpoint** server-side (`require_perm`); the UI only hides buttons.
`driver` and `customer` roles exist in the schema and permission map but have no screens yet (phase 3).

## Deploy (one VPS, Docker Compose + Caddy)

```bash
git clone <repo> /srv/hisaab && cd /srv/hisaab
cp .env.example .env && nano .env          # DOMAIN, POSTGRES_PASSWORD, POSTGRES_ADMIN_PASSWORD, JWT_SECRET (openssl rand -base64 48), admin login
docker compose up -d --build               # Caddy gets the HTTPS certificate automatically
```

* `api` runs `alembic upgrade head` and `app.bootstrap` on every start, then gunicorn + uvicorn workers.
* Postgres has **no published port**; only Caddy exposes 80/443. The app connects as a restricted role (not a
  superuser, owns only its own database); a separate admin login exists for restore tests. Secrets live in `.env`
  (git-ignored).
* **Backups**: the `backup` container dumps nightly at 02:00 (gzip-verified), keeps 30 daily + 12 monthly, and
  copies them off-site if `BACKUP_OFFSITE_REMOTE` is set (any rclone remote: Backblaze B2, S3…). On the 1st of each
  month at 04:00 it **restores the newest dump into a scratch database and checks the books balance**; it fails loudly
  if the backup is unusable. Run it by hand any time: `docker compose exec backup /scripts/restore-test.sh`.
* **Staging** (same VPS, separate DB/volumes, plain HTTP on :8080):
  `docker compose -p hisaab-staging -f docker-compose.yml -f docker-compose.staging.yml --env-file .env.staging up -d --build`
* **CI/CD**: `.github/workflows/ci.yml` lints, tests (on PostgreSQL), checks that migrations match the models, builds
  the images, and deploys over SSH on pushes to `main` (production) / `staging`. Set repo secrets
  `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`; without them the deploy step is skipped.

### Migrating from the registers (ARCHITECTURE.md §13)

1. Admin → *Masters*: customers, suppliers, materials, vehicles, staff, cash/bank accounts.
2. Admin → *Opening balances*: pick the cut-over date; enter party balances, staff advances, cash/bank, and the
   physical yard stock with rates. Re-saving replaces, it never doubles.
3. From that date enter everything in the portal; run paper in parallel 2–4 weeks and compare with the khata reports.

## Defaults chosen for the open client questions (ARCHITECTURE.md §15)

The schema supports every option; these are only defaults and are easy to change:

| Question | Default today | Where to change |
|---|---|---|
| Currency / locale | `Rs`, lakh grouping (`en-IN`) | `CURRENCY_SYMBOL`, `VITE_CURRENCY`, `VITE_LOCALE` |
| Financial year (challan numbering) | April–March | `FIN_YEAR_START_MONTH` |
| Tax | Optional per invoice (`tax_rate` entered when making the bill), posted to *Output Tax Payable* | invoice screen |
| Units | One unit per material, same for buying and selling | material master |
| Freight (bhara) | Separate optional field on the challan (income, credited to the vehicle) | challan screen |
| Rental basis | Hour / trip / day chosen per rental; diesel not netted | rental screen |
| Labour pay | Monthly / daily / per-trip per worker; overtime = 1× hourly (`daily ÷ 8`) | staff master, `OVERTIME_MULTIPLIER`, `WORKDAY_HOURS` |
| Diesel | Cash/bank *or* on credit from a pump (a supplier) | expense screen |
| History | Fresh start from a cut-over date with opening balances | opening-balances screen |

## Known limits and what is not built

* **Phase 3 is not built**: driver PWA, customer portal, SMS/WhatsApp *reminders*. The roles, `users.staff_id` /
  `party_id` links and permissions are in place. WhatsApp **sharing** of a khata works today without any API (a
  `wa.me` link opens the user's own WhatsApp with the statement text); sending automatic messages needs a provider.
* **Vehicle P&L revenue is freight + equipment rent only.** Material sale value is not vehicle revenue; if bhara is
  included in the material rate (freight left at 0), a trolley shows cost with no revenue. Decide with the client.
* Editing a challan/purchase re-prices its stock effect at the *current* average cost, not the historical one, and
  voiding a purchase is refused if its material has already been sold (void the sales first).
* Login rate limiting counts attempts per IP in the database (so it holds across workers); behind Caddy the real
  client IP comes from `X-Forwarded-For`.
* Excel/PDF exports are generic tables (no company letterhead/logo yet); challan, bill and voucher PDFs are basic
  A5/A4 layouts.
* Urdu/Hindi: the i18n structure (`frontend/src/i18n`) and RTL switch exist, but only English strings are provided,
  and many labels are still literal English in the components.
* Not done on purpose (per the architecture): Redis, queues, microservices, NoSQL, hard deletes, float money.
