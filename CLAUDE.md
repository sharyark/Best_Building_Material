# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Hisaab Portal replaces the paper registers of a small construction-material supplier (sand, cement, blocks, gravel, crush; 5 tractor-trolleys, 1 dumper, 3 loaders). Customer khata, supplier payments, yard stock, diesel, rentals, labour wages and advances live in one place, so balances, outstanding and profit always agree.

Two users, two login pages: the **owner/admin** (`/admin/login`: everything, including void, profit reports, users, opening balances, month lock, audit) and the **munshi/accountant** (`/accountant/login`: daily entries and edits only, no void or profit). `driver` and `customer` roles exist in the schema but their apps (phase 3) are not built.

`ARCHITECTURE.md` is the spec (its VPS/Caddy deployment plan is no longer used); `README.md` has the run/CI details and the defaults chosen for open client questions; `INSTALL.md` is the client-PC setup guide and `MANUAL.md` a user manual (both Roman Urdu); keep MANUAL.md's numbers in step with `app/seed_small.py`.

## Commands

One-shot local stack: `./dev.sh` (or `dev.ps1`/`dev.bat` on Windows) starts the dev Postgres, creates `backend/.venv` + `backend/.env` on first run, migrates, seeds, and runs API (:8000) and web (:5173). Run it, don't `source` it. `./dev_without_data.sh` / `dev_without_data.bat` (= `dev.sh --no-demo`, `dev.ps1 -NoDemo`) do the same but never load demo data: only `app.bootstrap` (first admin, cash account, chart), existing data untouched.

Backend (`cd backend && source .venv/bin/activate`):
```bash
ruff check . && ruff format --check .      # lint (line length 120; alembic/versions excluded)
pytest -q                                   # SQLite, fast
pytest tests/test_core_flow.py::test_name   # single test
TEST_DATABASE_URL=postgresql+psycopg://hisaab:hisaab@localhost:5432/hisaab_test pytest -q   # same suite on Postgres
pip install -e ".[dev]"                      # first-time deps (WeasyPrint needs system pango/harfbuzz libs)
alembic upgrade head                        # schema
alembic revision --autogenerate -m "..."    # after model changes; CI runs `alembic check` and fails if models drift
python -m app.seed [--reset] [--small]      # 45 days of demo data; --small = one of everything, one week (MANUAL.md walks through it); `python -m app.bootstrap` = only first admin
uvicorn app.main:app --reload               # :8000, docs at /api/docs
```
Local DB: `docker compose -f docker-compose.dev.yml up -d`, or set `DATABASE_URL=sqlite:///./dev.db` + `AUTO_CREATE_TABLES=true` in `backend/.env`. For local HTTP set `COOKIE_SECURE=false`.

Frontend (`cd frontend`):
```bash
npm run dev                  # :5173, proxies /api to 127.0.0.1:8000 (use 127.0.0.1, not localhost: IPv6 breaks the proxy)
npm run typecheck && npm run lint && npm test && npm run build
npx vitest run src/features/deliveries/ChallanForm.test.tsx   # single unit test
npx playwright test [-g "name"]   # e2e; needs seeded API + `npm run dev` running
```
Demo logins: owner `admin / admin12345` at `/admin/login`; munshi (accountant) `munshi / munshi12345` at `/accountant/login`.

E2E gotcha: login is rate-limited to 5/min/IP (DB-backed), so a full run can trip it; wait ~70s between runs. Refresh tokens rotate, so e2e shares one browser context per role. Tests expect the seeded demo data and are not all idempotent against a reused DB.

## Architecture (the parts that span many files)

**Hidden double-entry.** Users fill simple forms (challan, purchase, payment, diesel...). `backend/app/accounting/posting.py` is the *only* writer of journal entries/lines; each module service calls it in the same DB transaction as the document. Event → Dr/Cr mappings live in `accounting/rules.py`; the chart in `accounting/chart.py`. Never write journal rows anywhere else. Reports are queries over `journal_lines`; `accounting/balances.py` computes party/account balances.

**Document lifecycle rules** (all enforced in the service layer, tested in `tests/test_invariants.py`):
- No hard delete of financial documents: *void* (reason required) posts a reversal dated the same day; *edit* = reverse + re-post.
- Month lock (`period_locks`) blocks add/edit/void for any date in a locked month.
- Gap-free numbering via `doc_sequences` (financial-year based, `FIN_YEAR_START_MONTH`).
- `client_ref` makes POSTs idempotent.
- Stock uses a moving weighted average (`stock_items`, signed `stock_moves`); challans post COGS at the current average; Inventory ledger must equal yard-stock value.
- Money is `NUMERIC(14,2)` / `Decimal` / decimal *strings* in JSON. Never float.
- Vehicle P&L uses `vehicle_id` as a cost centre on journal lines; vehicle revenue = freight + rental only.

**Backend layout.** Feature modules in `app/modules/<name>/` (models/schemas/service/router); shared plumbing in `app/core/`. Every endpoint is guarded by `require_perm(...)` against the role→permission map in `core/permissions.py` (admin `*`, accountant limited; `driver`/`customer` exist but have no UI). New models must be imported in `app/models.py` for Alembic/tests. Errors are always `{code, message, details}` (`core/errors.py`). List endpoints take `?page=&size=&from=&to=&q=&sort=`.

**Audit.** `app/audit/hooks.py` uses SQLAlchemy Session events to write `audit_logs` automatically (one create row + merged update/void row per object per transaction, password fields redacted). The actor comes from `session.info["actor"]`, so any new write path must go through a session that has it set (see `core/deps.py`).

**Auth.** Short JWT access token (kept in memory only on the frontend) + rotating refresh token in an httpOnly SameSite=Strict cookie (stored hashed; reuse revokes all). Login takes an optional `portal` (`admin`|`accountant`); a role signing in on the wrong portal gets `WRONG_PORTAL` without revealing whether the user exists.

**Reports.** Each report builds a generic `ReportTable` that is rendered as JSON, Excel (openpyxl) or PDF (WeasyPrint); document PDFs (challan, invoice, voucher) are in `modules/reports`. Adding a report = one query function + registering it; the frontend `ReportPage` renders any table.

**Frontend.** `src/app/` holds router (lazy routes, `RequireAuth`), `AuthContext` (`useAuth().can(perm)`, `usePermission`) and layout. `src/features/<area>/` per screen; shared building blocks in `src/components/` (`Field` with id-linked labels, `EntitySelect` with inline quick-add via `QuickAdd.tsx`, `DocPage`, `DocFormShell`, `ReportView`, `StatCard`/`HeroBanner`); `ReportPage` is in `features/reports/` and `CrudTable` (masters lists) in `features/masters/`. Data via TanStack Query; after any save, invalidate all queries (balances are cross-cutting). Forms are RHF + Zod. UI hides actions by permission, but the server is the real gate. Currency/locale come from `VITE_CURRENCY`/`VITE_LOCALE`; i18n scaffolding is English-only.

**Deploy.** There is no server deployment: the portal runs on the client's PC with `dev_without_data.bat` (PostgreSQL in Docker via `docker-compose.dev.yml`, API and Vite directly on the PC; `alembic upgrade head` + `app.bootstrap` on every start, never demo data). Backups are manual `pg_dump`/`pg_restore` (`INSTALL.md`). CI (`.github/workflows/ci.yml`) only lints, tests on Postgres and checks migrations; it builds and deploys nothing.

## What belongs where

| Concern | Location |
|---|---|
| Journal writing, Dr/Cr rules, chart of accounts, balances, doc numbering | `backend/app/accounting/` (`posting.py`, `rules.py`, `chart.py`, `balances.py`, `sequences.py`) |
| A business document (challan, purchase, payment, expense, rental, invoice, labour, stock, masters, auth, reports) | `backend/app/modules/<name>/{models,schemas,service,router}.py` |
| Helpers shared by document services (`get_or_404`, `find_by_client_ref`, `ensure_active`), shared base models/schemas | `backend/app/modules/common*.py` |
| Config, DB session, errors, money, pagination, permissions, security, deps | `backend/app/core/` |
| Audit trail | `backend/app/audit/` |
| Migrations; seed/bootstrap | `backend/alembic/versions/`; `backend/app/{seed,bootstrap}.py` |
| Backend tests | `backend/tests/` (behaviour/invariants, not per-function) |
| Axios client + refresh handling, query hooks, lookups, API types | `frontend/src/api/` |
| Router, auth context, layout, providers | `frontend/src/app/` |
| One screen per area | `frontend/src/features/<area>/` (`XPage.tsx` list, `XForm.tsx` entry) |
| Reusable UI (Field, EntitySelect, QuickAdd, DocPage, Money, StatCard...) | `frontend/src/components/` |
| Formatting, dates, zod schemas, config | `frontend/src/lib/` |
| Permission/debounce hooks | `frontend/src/hooks/` |
| UI strings scaffolding | `frontend/src/i18n/` |
| Browser tests | `frontend/e2e/`; unit tests sit beside the file (`*.test.ts(x)`) |
| Running it (local and at the client), CI | `docker-compose.dev.yml`, `dev*.sh` / `dev*.bat` / `dev.ps1`, `INSTALL.md`, `.github/workflows/ci.yml` |

Layering rule (backend): router → service → posting engine/models. Routers only validate, authorise and call services; services hold business rules and call `posting.py`; nothing but `posting.py` creates journal rows.

## Code style

Backend (Python 3.12): ruff with rules `E,F,I,UP,B`, line length 120 (`E501` and `B008` ignored; `B008` because of FastAPI `Depends`). Format with `ruff format`. Modern typing (`X | None`, PEP 695 generics like `def f[T]`). Pydantic v2 schemas; SQLAlchemy 2 typed models. Raise the typed errors in `core/errors.py` (`NotFound`, `Conflict`, `Forbidden`...) with a stable `code`; never return ad-hoc error shapes. Comments explain *why*, not what.

Frontend (TypeScript strict): `noUnusedLocals/Parameters`; eslint runs with `--max-warnings 0`, unused vars must start with `_`. Use the `@/` alias for imports from `src`. Function components and hooks only; forms are React Hook Form + Zod (schemas in `lib/schemas.ts`); server state in TanStack Query, not component state. Reuse `components/` (`Field`, `EntitySelect`, `DecimalInput`, `Money`) rather than raw AntD inputs, so labels stay linked to inputs and money stays formatted. Match the surrounding code's comment density: sparse, explaining non-obvious choices.

## UI/UX: must be attractive

The owner asked for an attractive, moderate look: themed visuals, not "so much paint". Every new or changed screen must meet this bar, not just work.

- Build screens from the existing look: `HeroBanner` + `HeroArt` (construction-themed SVG, class `hero-art`), `StatCard`, `PageHeader`, AntD cards with soft spacing. Reuse them before inventing new styling; keep styles in `index.css` or the component, with colours from the existing palette (owner accent `#8a1f2d`, munshi accent `#1f4e79`).
- Moderate, not loud: one accent colour per screen, generous whitespace, no more than a couple of decorative elements per page, no clutter. Themed (sand, cement, trucks, yard) beats generic.
- Never ship a bare table or form on a blank page: give it a clear header, an empty state with a hint, a loading state, and friendly success/error feedback.
- Daily-entry screens (challan etc.) favour speed: large touch targets, keyboard-first (type, Enter, save, form resets), readable numbers via `Money`/`formatMoney`.
- Responsive: must work at phone width with no sideways page scroll (e2e checks this); the munshi often uses a phone.
- Both light-theme readability and sufficient contrast; labels linked to inputs (`Field`).
- After a UI change, look at it in the browser (or a Playwright screenshot) before calling it done.

## Text and data constraints

- **Money**: `NUMERIC(14,2)` in the DB, `Decimal` in Python, decimal *strings* in JSON, never `float`/JS number for storage or posting. On screen use `formatMoney` / `formatCurrency` / `formatDrCr` from `lib/format.ts` (lakh grouping via `VITE_LOCALE`, currency from `VITE_CURRENCY`; backend default `Rs`). Debit-positive signed balances display as `Dr`/`Cr`.
- **Quantities**: up to 3 decimals (`formatQty`); one unit per material.
- **UI wording**: English only today; plain shop-floor words (challan, khata, munshi, bhara/freight), no accounting jargon (debit/credit/journal) in the accountant's screens. Put new user-facing strings through `i18n/en.ts` keys where the surrounding code does; many existing labels are still literal. API error `message`s are shown to users, so write them as full sentences a munshi can act on (e.g. `"This document is void and cannot be changed"`), and give every error a stable machine `code`.
- **Voiding** requires a typed reason; there are no delete buttons or `DELETE` endpoints on financial documents.
- **Dates**: ISO `YYYY-MM-DD` over the wire; document numbers are gap-free per financial year.
- **Secrets**: `.env` is git-ignored; only `.env.example` files are committed.
