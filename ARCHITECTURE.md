# Construction Material Supply – Digital Hisaab Portal
### System Architecture v1 (draft)

---

## 1. Business in one paragraph

A small construction-material supplier. Fleet: **5 tractor-trolleys, 1 dumper, 3 loaders**.
Sells and delivers **rait (sand), cement, blocks, bajri (gravel), crush** and other building material.

**Three income/cost streams (confirmed by client):**
1. **Material trading via own yard:** buy from crusher / bhatta / dealer → material is **stocked in the yard** → sold and delivered to customer sites.
2. **Equipment rental:** loaders / dumper / tractors hired out per hour / trip / day.
3. **Labour & staff payroll:** drivers, operators and **all labour** (loading/unloading, helpers), with attendance, wages and advances.

```
 Supplier (crusher/bhatta/dealer) ──purchase──► YARD STOCK ──challan/trip──► Customer site
                                                    ▲
                 Own vehicles bring material in ────┘   (diesel, driver cost tracked)
```

Today the whole hisaab lives in registers: customer khata, supplier payments, diesel, driver advances, repairs.
**Goal:** move every entry to a web portal, so balances, outstanding and profit always match and can be checked from anywhere.

### Users

| Role | Phase | What they do |
|---|---|---|
| **Admin** (owner) | 1 | Everything: reports, profit, void/delete, user management, month lock |
| **Accountant** (munshi) | 1 | Daily entries: challan, payment, diesel, expenses, salary. No delete, no user mgmt |
| **Driver** | 3 (later) | Mobile: log own trips and diesel, see own advance/salary |
| **Customer** | 3 (later) | View own khata statement and bills |

The schema and permission system include the Driver and Customer roles from day 1, so they can be switched on later without a redesign.

---

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | **React 18 + Vite + TypeScript** | Required. TypeScript catches money/field bugs at compile time |
| UI kit | **Ant Design 5** | Best ready-made Table, Form, DatePicker, Select for data-entry admin apps, so we build little UI by hand |
| Server state | **TanStack Query** | Caching, refetch after save, loading/error states |
| Forms | **React Hook Form + Zod** | Fast forms, the same validation rules as the backend |
| Routing | **React Router v6** | Standard |
| Backend | **FastAPI (Python 3.12)** | Required. Auto OpenAPI docs, Pydantic validation |
| ORM / migrations | **SQLAlchemy 2.0 + Alembic** | Mature; real transactions; versioned schema changes |
| Validation | **Pydantic v2** | Comes with FastAPI |
| Auth | **JWT** (access 15 min + refresh in httpOnly cookie), **Argon2** password hash | Secure, stateless |
| PDF | **WeasyPrint** (HTML → PDF) | Khata statements, bills, challans |
| Excel | **openpyxl** | Export of any report |
| Database | **PostgreSQL 17** | See section 3 |
| Deploy | **Docker Compose on 1 VPS + Caddy** (auto HTTPS) | Cheap, simple, enough for this scale |

---

## 3. Database decision: PostgreSQL

### Comparison

| Criteria | **PostgreSQL** | MySQL / MariaDB | MongoDB | SQLite |
|---|---|---|---|---|
| ACID transactions (money must never half-save) | ✅ Excellent | ✅ Good | ⚠️ Possible but not its nature | ✅ but single writer |
| Relational data (customer → challan → bill → payment) | ✅ | ✅ | ❌ Joins are painful | ✅ |
| Exact money type `NUMERIC(14,2)` | ✅ | ✅ `DECIMAL` | ⚠️ Decimal128, clumsy | ⚠️ stores as text/real |
| CHECK constraints, partial indexes, triggers | ✅ Strongest | ⚠️ Weaker CHECK history | ❌ | ⚠️ Limited |
| Reports: window functions for running balance, CTEs | ✅ Best | ✅ (8.0+) | ⚠️ Aggregation pipeline | ✅ |
| `JSONB` for audit log (before/after snapshot) | ✅ Indexed | ⚠️ JSON, weaker | ✅ | ⚠️ |
| Multi-user (admin + accountant + future drivers) | ✅ | ✅ | ✅ | ❌ Not for a web server |
| FastAPI / SQLAlchemy / Alembic support | ✅ First class | ✅ | ❌ Different ODM | ✅ |
| Cost | Free | Free | Free | Free |

### Verdict

**PostgreSQL.** This app is basically an **accounting system**: every challan and payment changes balances, and a half-saved transaction would corrupt the khata. The data is highly relational, which rules out MongoDB, and SQLite cannot handle multiple users on a server. MySQL would work, but PostgreSQL has stricter data integrity (CHECK constraints, exact NUMERIC, transactional DDL in migrations), better reporting SQL and JSONB for the audit trail.

**Scale check:** about 50–100 trips a day is roughly 35k rows a year. PostgreSQL handles this on a ₹500/month VPS with no tuning, so we do **not** need Redis, queues, microservices or read replicas.

---

## 4. System overview

```
 ┌────────────────────────┐        ┌─────────────────────────┐
 │  Admin (mobile/laptop) │        │ Accountant (office PC)  │
 └───────────┬────────────┘        └────────────┬────────────┘
             │            HTTPS                 │
             └──────────────┬───────────────────┘
                            ▼
 ┌──────────────────────── VPS (Docker Compose) ────────────────────────┐
 │                                                                     │
 │   ┌───────────────────────────────┐                                 │
 │   │ Caddy (reverse proxy + TLS)   │                                 │
 │   │  /        → React static build│                                 │
 │   │  /api/*   → FastAPI           │                                 │
 │   └──────────────┬────────────────┘                                 │
 │                  ▼                                                  │
 │   ┌───────────────────────────────────────────────┐                 │
 │   │ FastAPI (gunicorn + uvicorn workers)          │                 │
 │   │  Routers → Services → Posting Engine → ORM    │                 │
 │   └──────────────┬────────────────────────────────┘                 │
 │                  ▼                                                  │
 │   ┌───────────────────────────┐    ┌──────────────────────────────┐ │
 │   │ PostgreSQL 17             │───►│ Nightly pg_dump (cron)       │ │
 │   │ (volume on disk)          │    │ → off-site storage (B2 / S3) │ │
 │   └───────────────────────────┘    └──────────────────────────────┘ │
 └─────────────────────────────────────────────────────────────────────┘
```

**Style:** a **modular monolith**: one FastAPI app, split internally into clean modules. It is easy to build, deploy and debug, and a module can still be pulled out later if ever needed (it almost certainly won't be).

---

## 5. Core design principle: hidden double-entry accounting

This is the most important decision in the whole system.

The accountant never sees debit/credit. They only fill simple forms (challan, payment, diesel). Behind each form, the backend's **Posting Engine** writes a **balanced journal entry** (total debit = total credit) **in the same DB transaction** as the document.

### Why this matters
- **Books can never go out of balance**, which is exactly the problem with paper registers.
- **Every report comes from one source of truth:** customer khata, supplier khata, cash book, vehicle profit and monthly P&L are all just queries on `journal_lines`.
- Adding a new feature (rental, salary, stock) only means adding a new posting rule. Reports don't change.

### Posting rules (examples)

| Business event | Debit (Dr) | Credit (Cr) |
|---|---|---|
| Purchase into yard: 10 trolley rait from Crusher X @ 2,000 | Inventory – Material | Supplier: Crusher X |
| Challan from yard: 1 trolley rait to Customer A @ 3,000 | Customer A | Sales – Material |
| …same challan, cost at weighted-avg 2,000 (auto) | Cost of Goods Sold | Inventory – Material |
| Bhara (freight) charged separately | Customer A | Income – Freight |
| Loader rented 4 hrs @ 1,200 | Customer B | Income – Equipment Rent |
| Cash received from Customer A 5,000 | Cash in Hand | Customer A |
| Paid Crusher X by bank 10,000 | Supplier: Crusher X | Bank – HBL/SBI |
| Diesel 1,500 for Tractor-1, on pump credit | Expense – Diesel *(vehicle = T1)* | Supplier: Petrol Pump |
| Driver Ali takes advance 2,000 cash | Staff: Ali | Cash in Hand |
| Monthly salary of Ali 18,000 | Expense – Salary *(vehicle = T1)* | Staff: Ali |
| Opening balance from old register | Customer / Supplier | Opening Balance Equity |
| Opening yard stock | Inventory – Material | Opening Balance Equity |
| Labour attendance (daily wage) for the day | Expense – Labour Wages | Staff: labourer |
| Stock shortage / wastage adjustment | Expense – Stock Loss | Inventory – Material |

`vehicle_id` on a journal line acts as a **cost centre**, which gives **profit per vehicle** for free.

### Stock valuation: moving weighted average
Each purchase updates the material's average cost: `new_avg = (old_qty×old_avg + in_qty×in_rate) / (old_qty+in_qty)`.
Each challan posts COGS at the current average, so **profit per challan and per material is exact**, and the yard stock value is always known.
Sand and crush lose volume (wind, rain, measuring differences), so a periodic **physical count → stock adjustment** posts the difference to *Stock Loss*.

### Correction rules (accounting-grade)
- **No hard delete** of any financial document. Admin can **void** with a reason, and the engine posts a **reversal** journal.
- **Edit** = reverse old journal + post new one, in one transaction. The audit log keeps before/after.
- **Month lock:** admin locks a closed month. After that nobody can add, edit or void entries dated in it.

---

## 6. Modules

```
┌──────────────┬──────────────────────────────────────────────────────────┐
│ Module       │ Contents                                                 │
├──────────────┼──────────────────────────────────────────────────────────┤
│ auth         │ login, refresh, logout, users, roles, permissions         │
│ masters      │ parties (customer/supplier), sites, materials, vehicles,  │
│              │ staff, rate cards, cash/bank accounts                     │
│ purchases    │ purchases INTO yard (with inbound vehicle/driver)         │
│ stock        │ yard stock: avg cost, live balance, physical-count adjust │
│ deliveries   │ challan / trip OUT of yard to customer site               │
│ rentals      │ loader/dumper/tractor hire per hour / trip / day          │
│ invoices     │ group challans into a bill (weekly/monthly, tax optional) │
│ payments     │ money in (receipts) / money out (to supplier, staff)      │
│ expenses     │ diesel, repair, tyre, insurance, toll, office, misc       │
│ labour       │ all workers: attendance, daily/monthly/per-trip wages,    │
│              │ advances, weekly/monthly settlement, worker khata         │
│ accounting   │ chart of accounts, posting engine, journals, month lock   │
│ reports      │ khata, outstanding, cash book, vehicle P&L, P&L, day book │
│ audit        │ who changed what, when (before/after JSON)                │
└──────────────┴──────────────────────────────────────────────────────────┘
```

---

## 7. Database schema

Conventions: `id BIGSERIAL`, money `NUMERIC(14,2)`, quantities `NUMERIC(12,3)`, every table has `created_at, created_by, updated_at`. Transaction tables also have `status ('active'|'void')`, `void_reason` and `client_ref UUID UNIQUE` (idempotency: a double-click won't create two challans).

### 7.1 Auth
```
users           id, name, phone UNIQUE, email, password_hash, role,
                staff_id NULL → staff   (for future Driver login)
                party_id NULL → parties (for future Customer login)
                is_active, last_login_at
refresh_tokens  id, user_id, token_hash, expires_at, revoked_at
```
Roles: `admin | accountant | driver | customer`. Permissions are a role → permission map in code (e.g. `challan.create`, `challan.void`, `report.profit`).

### 7.2 Masters
```
parties         id, type ('customer'|'supplier'|'both'), name, phone, address,
                tax_no, account_id → accounts, is_active
                -- supplier examples: crusher, bhatta (block kiln), cement dealer, petrol pump
sites           id, party_id, name, address            -- 1 customer, many construction sites
materials       id, name, unit ('trolley'|'cft'|'ton'|'bag'|'piece'|'brass'),
                default_sale_rate, default_purchase_rate, hsn_code NULL, is_active
rate_cards      id, party_id, material_id, rate, effective_from   -- customer-specific rates
vehicles        id, type ('tractor_trolley'|'dumper'|'loader'), reg_no, name,
                capacity, meter_type ('km'|'hours'), is_active
staff           id, name, phone, role ('driver'|'operator'|'labour'|'helper'|'munshi'),
                wage_type ('monthly'|'daily'|'per_trip'), wage_amount,
                default_vehicle_id NULL, account_id → accounts, is_active
money_accounts  id, name ('Cash in Hand', 'Bank – XYZ', 'JazzCash/UPI'), account_id → accounts
```

### 7.3 Transactions
```
purchases       id, bill_no, supplier_slip_no, date, supplier_id, total,
(into yard)     vehicle_id NULL, driver_id NULL,   -- own vehicle brought it in
                transport_by ('own'|'supplier'), journal_id, status
purchase_lines  id, purchase_id, material_id, qty, rate, amount
deliveries      id, challan_no (per financial year), date,
(challan, from  customer_id, site_id, material_id, qty, unit, sale_rate, sale_amount,
 yard)          freight_amount, cost_rate (avg cost snapshot), cost_amount,
                vehicle_id, driver_id, invoice_id NULL, journal_id, status, notes
rentals         id, date, customer_id, site_id, vehicle_id, operator_id,
                basis ('hour'|'trip'|'day'), qty, rate, amount, journal_id, status
invoices        id, invoice_no, date, customer_id, site_id NULL, period_from, period_to,
                subtotal, tax_rate, tax_amount, total, is_tax_invoice, journal_id, status
payments        id, voucher_no, date, direction ('in'|'out'),
                party_id NULL, staff_id NULL, money_account_id, mode
                ('cash'|'bank'|'cheque'|'online'), ref_no, amount, journal_id, status
expenses        id, date, category ('diesel'|'repair'|'tyre'|'insurance'|'toll'|
                'office'|'misc'), vehicle_id NULL, amount, litres NULL, meter_reading NULL,
                paid_via ('money_account'|'party_credit'), money_account_id NULL,
                party_id NULL, journal_id, status, notes
attendance      id, date, staff_id, status ('present'|'half'|'absent'), overtime_hours,
                site_id NULL, vehicle_id NULL     -- daily-wage labour accrues per day
                UNIQUE (date, staff_id)
wage_settlements id, staff_id, period_from, period_to, days, trips, gross,
                advances_adjusted, deductions, net_payable, journal_id, status
                -- monthly staff: accrual at month end; daily labour: per attendance
stock_items     material_id PK, qty_on_hand, avg_cost, value   -- maintained by engine
stock_moves     id, date, material_id, qty_in, qty_out, rate, value,
                source_type ('purchase'|'delivery'|'adjustment'|'opening'), source_id
stock_counts    id, date, material_id, system_qty, physical_qty, diff, journal_id
```

### 7.4 Accounting core
```
accounts        id, code, name, type ('asset'|'liability'|'income'|'expense'|'equity'),
                is_system, parent_id NULL
journal_entries id, date, source_type, source_id, narration,
                reverses_id NULL → journal_entries, created_by
journal_lines   id, journal_id, account_id, debit, credit, vehicle_id NULL
                CHECK (debit >= 0 AND credit >= 0 AND (debit = 0) <> (credit = 0))
period_locks    month (DATE PK), locked_by, locked_at
doc_sequences   doc_type, fin_year, last_no            -- gap-free challan/bill numbers
audit_logs      id, user_id, action, entity, entity_id, before JSONB, after JSONB,
                ip, at
```
Key indexes: `journal_lines(account_id, journal_id)`, `journal_entries(date)`, `deliveries(customer_id, date)`, `deliveries(vehicle_id, date)`, `expenses(vehicle_id, date)`.

A **party balance** is `SUM(debit - credit)` over its account's lines. The khata statement uses a window function for the running balance.

---

## 8. Backend structure (FastAPI)

```
backend/
├── app/
│   ├── main.py                  # app factory, routers, middleware
│   ├── core/
│   │   ├── config.py            # pydantic-settings, .env
│   │   ├── db.py                # engine, session, transaction helper
│   │   ├── security.py          # argon2, JWT
│   │   ├── deps.py              # get_db, get_current_user, require_perm("x")
│   │   └── errors.py            # domain exceptions → HTTP responses
│   ├── accounting/
│   │   ├── models.py            # accounts, journals, period_locks
│   │   ├── posting.py           # ★ Posting Engine (the only writer of journals)
│   │   └── rules.py             # event → Dr/Cr mapping
│   ├── modules/
│   │   ├── auth/      {models, schemas, service, router}.py
│   │   ├── masters/   ...
│   │   ├── deliveries/...
│   │   ├── payments/  ...
│   │   ├── expenses/  ...
│   │   ├── stock/     ...   # avg-cost calc, stock moves
│   │   ├── rentals/   ...
│   │   ├── labour/    ...   # attendance, wage settlement
│   │   ├── invoices/  ...
│   │   └── reports/   {queries, pdf, excel, router}.py
│   └── audit/                   # SQLAlchemy event hooks → audit_logs
├── alembic/                     # migrations
├── tests/                       # pytest against a real Postgres (docker)
└── pyproject.toml
```

**Request flow:** `router` (HTTP, auth, validation) → `service` (business rules, inside one DB transaction) → `posting.post(event)` → commit. If any step fails, **everything rolls back**.

### API conventions
- Prefix `/api/v1`; REST nouns (`/deliveries`, `/payments`, `/reports/khata/{party_id}`)
- List endpoints: `?page=&size=&from=&to=&q=&sort=`
- Void: `POST /deliveries/{id}/void {reason}`. No `DELETE` on financial docs.
- Errors: `{ "code": "PERIOD_LOCKED", "message": "...", "details": {} }`
- OpenAPI docs at `/api/docs` (admin only in production)

---

## 9. Frontend structure (React + Vite)

```
frontend/src/
├── app/            # router, providers (QueryClient, AntD theme, auth)
├── api/            # axios client, interceptors (refresh token), typed endpoints
├── features/
│   ├── auth/           # login, user management
│   ├── dashboard/      # today's trips, cash in hand, total receivable/payable
│   ├── masters/        # customers, suppliers, sites, materials, vehicles, staff
│   ├── deliveries/     # challan entry (fast, keyboard-friendly), list
│   ├── payments/       # receipt / payment voucher
│   ├── expenses/       # diesel & expense entry
│   ├── stock/          # yard stock, physical count
│   ├── rentals/        # equipment hire
│   ├── labour/         # attendance sheet (grid: workers × days), settlement
│   ├── invoices/       # pick challans → generate bill → PDF
│   └── reports/        # khata, outstanding, cash book, vehicle P&L, P&L
├── components/     # shared: MoneyInput, PartySelect, DateRangePicker, PrintButton
├── hooks/          # usePermission, useDebounce
└── lib/            # formatMoney, date (DD-MM-YYYY), zod schemas
```

### UX rules for this client
- **Attendance screen** is a grid: all workers × days of the week, tap to mark present/half/absent.
- **Stock warning** on challan if the yard quantity would go negative.
- **Challan entry is the hottest screen.** It should be keyboard-first, remember the last vehicle and driver, auto-fill the rate from the rate card, and save then reset for the next entry in under 10 seconds.
- **Responsive:** the owner will check reports on a phone.
- **Khata statement → PDF / WhatsApp share** button on every party.
- Buttons are hidden or disabled by permission (Accountant does not see Void / Profit).
- Labels can be shown in Urdu/Hindi later via i18n (structure ready, English first).

---

## 10. Reports (all derived from the journal)

| Report | Who | Answers |
|---|---|---|
| Dashboard | Admin, Accountant | Today's trips, cash in hand, total receivable, total payable |
| Customer khata statement | Both | Date-wise Dr/Cr with running balance, PDF/WhatsApp |
| Supplier khata | Both | How much we owe crusher / bhatta / pump |
| Outstanding / aging | Admin | Who owes how much, for how long (0-30, 31-60, 60+ days) |
| Cash book / bank book | Both | Daily money in/out, closing balance |
| Day book | Both | Every entry of a date |
| **Vehicle P&L** | Admin | Per vehicle: trips, revenue, diesel, repair, driver salary → profit |
| Material margin | Admin | Per material: sale vs purchase rate, total margin |
| Labour / driver khata | Both | Attendance, wages earned, advances, balance payable |
| Labour cost summary | Admin | Total wages per week/month, per site / vehicle |
| Rental income | Admin | Hours/trips per machine, income, unpaid rent |
| Monthly P&L | Admin | Income − expenses |
| **Yard stock** | Both | Opening + in − out ± adjustment = closing qty and value |

All reports can be exported to Excel and PDF.

---

## 11. Security & reliability

- HTTPS only (Caddy auto-TLS); CORS locked to the portal domain
- Argon2 password hashing; login rate-limited (5 tries/min/IP)
- Access JWT 15 min (memory) + refresh token in an **httpOnly, Secure, SameSite=Strict** cookie, rotated on use and stored hashed for revoke
- Permission check on **every** endpoint server-side; frontend hiding is cosmetic only
- DB user for the app has no superuser rights; Postgres port is not exposed publicly
- **Backups:** nightly `pg_dump` → compressed → off-site bucket; keep 30 daily + 12 monthly; **restore tested monthly**
- Audit log on every create/update/void
- Secrets in `.env` on the server, never in git

---

## 12. Deployment

```
docker-compose.yml
├── caddy      ports 80/443, serves /frontend/dist, proxies /api → api:8000
├── api        FastAPI image, runs `alembic upgrade head` on start
├── db         postgres:17, named volume, no public port
└── backup     cron container: pg_dump → B2/S3
```
- VPS: 2 vCPU / 2–4 GB RAM (Hetzner / DigitalOcean / Contabo / local provider), ~₹500–1,000/month
- CI (GitHub Actions): lint + tests → build images → deploy via SSH
- Separate **staging** compose stack on the same VPS for testing before release

---

## 13. Data migration from registers

1. Enter masters: customers, suppliers, materials, vehicles, staff.
2. Pick a **cut-over date** (e.g. 1st of next month).
3. Enter **opening balances** per party, staff advance, cash and bank as of that date, plus a **physical count of yard stock with rates** (one screen, posts to Opening Balance Equity).
4. From the cut-over date, all entries go in the portal. Old registers are archived, not re-typed.
5. Run paper and portal in parallel for 2–4 weeks, then match balances.

---

## 14. Delivery phases

| Phase | Scope | Rough effort* |
|---|---|---|
| **1 – MVP** | Auth (admin, accountant), masters, opening balances (party + stock + staff), **purchases into yard, yard stock (avg cost), challans from yard**, **rentals**, **labour attendance + wages + advances**, payments in/out, expenses + diesel, posting engine, khata + cash book + stock + dashboard, audit log, backups | 7–9 weeks |
| **2 – Business depth** | Invoices/bills (+ tax), vehicle P&L, material margin, outstanding/aging, physical stock count, PDF/WhatsApp share, month lock | 3–4 weeks |
| **3 – Extended users** | Driver PWA (trip + diesel entry, own statement), customer portal (khata + bills), SMS/WhatsApp payment reminders | 4–6 weeks |

\*For one full-stack developer.

### What we are deliberately NOT doing (and why)
- **Microservices, Kafka, Redis:** this scale doesn't need them, and they would add cost and failure points.
- **NoSQL:** financial relational data needs ACID and joins.
- **Hard delete of entries:** it would destroy trust in the books.
- **Float for money:** it causes rounding errors; we always use `NUMERIC`.

---

## 15. Open questions for the client

**Answered:** users = Admin + Accountant (Driver/Customer later) · material is stocked in own yard · loaders etc. are rented out · all labour pay must be tracked.

Still open (the schema already supports every option; these set screens and defaults):

1. **Tax:** does any customer need a tax invoice (GST / sales tax)? Which country and currency?
2. **Units:** how is each material bought and sold: per trolley, cft, ton, brass, bag, piece? Same unit for buying and selling?
3. **Billing cycle:** is each challan paid separately, or is a weekly/monthly bill made per customer/site?
4. **Freight:** is bhara charged separately or included in the material rate?
5. **Rental basis:** per hour, per trip or per day? Is diesel included in the rent or the customer's?
6. **Labour pay:** which workers are monthly, daily-wage or per-trip? Paid weekly or monthly? Is attendance kept today?
7. **Diesel:** paid cash, or on credit from a fixed pump?
8. **History:** start fresh from a cut-over date with opening balances (recommended), or enter old records too?
