"""Realistic demo data for the portal. Everything goes through the real services, so every journal balances.

    python -m app.seed           # adds demo data to an empty database
    python -m app.seed --reset   # (dev only) wipes all tables first

Demo logins: admin / admin12345 (owner) and munshi / munshi12345 (accountant).
"""

import argparse
import datetime as dt
import random
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select, text

from app.accounting.balances import balance_of
from app.accounting.models import Account
from app.accounting.schemas import OpeningBalanceIn
from app.accounting.service import set_opening_balance
from app.audit.hooks import install_audit_hooks, set_actor
from app.bootstrap import bootstrap
from app.core.config import get_settings
from app.core.db import Base, SessionLocal, engine
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.deliveries import service as deliveries
from app.modules.deliveries.schemas import DeliveryIn
from app.modules.expenses import service as expenses
from app.modules.expenses.schemas import ExpenseIn
from app.modules.invoices import service as invoices
from app.modules.invoices.schemas import InvoiceIn
from app.modules.labour import service as labour
from app.modules.labour.schemas import AttendanceIn, SettlementIn
from app.modules.masters import service as masters
from app.modules.masters.models import Material, MoneyAccount, Party, Staff, Vehicle
from app.modules.masters.schemas import (
    MaterialIn,
    MoneyAccountIn,
    PartyIn,
    RateCardIn,
    SiteIn,
    StaffIn,
    VehicleIn,
)
from app.modules.payments import service as payments
from app.modules.payments.schemas import PaymentIn
from app.modules.purchases import service as purchases
from app.modules.purchases.schemas import PurchaseIn, PurchaseLineIn
from app.modules.rentals import service as rentals
from app.modules.rentals.schemas import RentalIn
from app.modules.stock import service as stock
from app.modules.stock.models import StockItem

DAYS = 45

MATERIALS = [  # name, unit, sale rate, purchase rate
    ("Rait (Sand)", "trolley", 3300, 2000),
    ("Bajri (Gravel)", "trolley", 4000, 2500),
    ("Crush", "trolley", 4600, 3000),
    ("Cement", "bag", 1520, 1320),
    ("Blocks", "piece", 92, 62),
]
CUSTOMERS = [
    ("Ali Builders", "0300-1112233", ["Plot 12, Gulshan", "Mall Road site"]),
    ("Khan Construction", "0301-2223344", ["Housing Scheme Ph-2"]),
    ("Raza Developers", "0302-3334455", ["Tower A", "Tower B"]),
    ("Haji Imran", "0303-4445566", ["Residence Canal Rd"]),
    ("Noor Contractors", "0304-5556677", ["Bridge site"]),
    ("Sheikh & Sons", "0305-6667788", ["Warehouse"]),
    ("Malik Brothers", "0306-7778899", ["Plaza foundation"]),
    ("City Infra Ltd", "0307-8889900", ["Ring road package 3"]),
]
SUPPLIERS = [("Crusher X", ["Rait (Sand)", "Bajri (Gravel)", "Crush"]), ("Al-Fazal Bhatta", ["Blocks"]),
             ("Bestway Cement Dealer", ["Cement"]), ("National Petrol Pump", [])]  # fmt: skip


def run(db) -> None:
    rnd = random.Random(42)
    today = dt.date.today()
    cutover = today - dt.timedelta(days=DAYS)
    admin = db.scalar(select(User).where(User.role == "admin"))
    set_actor(db, admin.id)
    if not db.scalar(select(User.id).where(User.phone == "munshi")):
        db.add(User(name="Munshi", phone="munshi", password_hash=hash_password("munshi12345"), role="accountant"))

    # ---- masters --------------------------------------------------------------------------------
    cash = db.scalar(select(MoneyAccount).where(MoneyAccount.name == "Cash in Hand"))
    bank = masters.create_money_account(db, MoneyAccountIn(name="Bank - HBL", kind="bank"))
    materials = {
        name: masters.create_material(
            db,
            MaterialIn(
                name=name,
                unit=unit,
                default_sale_rate=sale,
                default_purchase_rate=buy,
                # loose material: one dumper ~ 3 trolleys, one loader bucket ~ a quarter trolley
                **({"dumper_qty": Decimal(3), "bucket_qty": Decimal("0.25")} if unit == "trolley" else {}),
            ),
        )  # fmt: skip
        for name, unit, sale, buy in MATERIALS
    }
    customers, sites = [], {}
    for name, phone, site_names in CUSTOMERS:
        c = masters.create_party(db, PartyIn(type="customer", name=name, phone=phone))
        customers.append(c)
        sites[c.id] = [masters.create_site(db, SiteIn(party_id=c.id, name=s)) for s in site_names]
    suppliers = {n: masters.create_party(db, PartyIn(type="supplier", name=n)) for n, _ in SUPPLIERS}
    pump = suppliers["National Petrol Pump"]
    for c in customers[:3]:  # negotiated rates for the big customers
        for m in list(materials.values())[:3]:
            card = RateCardIn(party_id=c.id, material_id=m.id, rate=m.default_sale_rate - 150, effective_from=cutover)
            masters.upsert_rate_card(db, card)
    trolleys = [masters.create_vehicle(db, VehicleIn(type="tractor_trolley", name=f"Tractor-{i}", reg_no=f"LEA-{1000 + i}")) for i in range(1, 6)]  # fmt: skip
    dumper = masters.create_vehicle(db, VehicleIn(type="dumper", name="Dumper-1", reg_no="LEB-7788", capacity=Decimal("12")))  # fmt: skip
    loaders = [masters.create_vehicle(db, VehicleIn(type="loader", name=f"Loader-{i}", meter_type="hours")) for i in range(1, 4)]  # fmt: skip
    fleet = [*trolleys, dumper]
    drivers = [
        masters.create_staff(
            db, StaffIn(name=n, role="driver", wage_type="monthly", wage_amount=w, default_vehicle_id=v.id)
        )
        for (n, w), v in zip(
            [
                ("Ali Raza", 22000),
                ("Bashir", 21000),
                ("Chaudhry Aslam", 21000),
                ("Dilawar", 20000),
                ("Ehsan", 20000),
                ("Farooq", 24000),
            ],
            fleet,
            strict=True,
        )  # fmt: skip
    ]
    operators = [
        masters.create_staff(
            db, StaffIn(name=n, role="operator", wage_type="monthly", wage_amount=26000, default_vehicle_id=v.id)
        )
        for n, v in zip(["Gulzar", "Hanif", "Iqbal"], loaders, strict=True)
    ]
    labour_crew = [
        masters.create_staff(db, StaffIn(name=n, role="labour", wage_type="daily", wage_amount=900))
        for n in ["Raju", "Sadiq", "Tariq", "Usman", "Waseem", "Yasir"]
    ]
    helper = masters.create_staff(db, StaffIn(name="Zafar", role="helper", wage_type="per_trip", wage_amount=150, default_vehicle_id=trolleys[0].id))  # fmt: skip
    db.flush()

    # ---- opening position at cut-over -----------------------------------------------------------
    openings = [("party", customers[0].id, "dr", 85000), ("party", customers[1].id, "dr", 42000),
                ("party", customers[2].id, "dr", 120000), ("party", customers[5].id, "dr", 15500),
                ("party", suppliers["Crusher X"].id, "cr", 60000), ("party", pump.id, "cr", 18000),
                ("money_account", cash.id, "dr", 250000), ("money_account", bank.id, "dr", 900000),
                ("staff", drivers[0].id, "dr", 5000)]  # fmt: skip
    for kind, ref, side, amount in openings:
        set_opening_balance(db, OpeningBalanceIn(date=cutover, kind=kind, ref_id=ref, side=side, amount=amount))
    for name, qty, rate in (("Rait (Sand)", 40, 1900), ("Bajri (Gravel)", 25, 2400), ("Crush", 30, 2900), ("Cement", 600, 1300), ("Blocks", 4000, 60)):  # fmt: skip
        stock.set_opening_stock(db, date=cutover, material_id=materials[name].id, qty=Decimal(qty), rate=Decimal(rate))
    db.commit()

    # ---- day-by-day activity --------------------------------------------------------------------
    def supplier_for(material: str) -> Party:
        return next(suppliers[n] for n, ms in SUPPLIERS if material in ms)

    def restock(day: dt.date, name: str, qty: int) -> None:
        m = materials[name]
        purchases.create(db, PurchaseIn(
            date=day, supplier_id=supplier_for(name).id, supplier_slip_no=f"SL-{rnd.randint(1000, 9999)}",
            transport_by=rnd.choice(["own", "supplier"]), vehicle_id=rnd.choice(fleet).id,
            lines=[PurchaseLineIn(material_id=m.id, qty=Decimal(qty), rate=(Decimal(m.default_purchase_rate) * Decimal(str(round(rnd.uniform(0.96, 1.06), 3)))).quantize(Decimal('0.01')))],
        ))  # fmt: skip

    # One customer pays every challan on the spot; another works off an advance paid up front.
    cash_customer, advance_customer, slow_payer = customers[6], customers[3], customers[4]
    payments.create(db, PaymentIn(
        date=cutover + dt.timedelta(days=1), direction="in", party_id=advance_customer.id, mode="bank",
        money_account_id=bank.id, amount=Decimal(200000), notes="Advance for the season",
    ))  # fmt: skip

    month_ends: set[dt.date] = set()
    for offset in range(1, DAYS + 1):
        day = cutover + dt.timedelta(days=offset)
        if day.weekday() == 6 and rnd.random() < 0.7:  # most Sundays are off
            continue
        for name, minimum, batch in (("Rait (Sand)", 12, 40), ("Bajri (Gravel)", 10, 30), ("Crush", 10, 30), ("Cement", 150, 400), ("Blocks", 1500, 3000)):  # fmt: skip
            item = db.get(StockItem, materials[name].id)
            if item.qty_on_hand < minimum:
                restock(day, name, batch)
        for _ in range(rnd.randint(5, 10)):
            cust = rnd.choice(customers)
            name = rnd.choices(list(materials), weights=[34, 20, 18, 16, 12])[0]
            m = materials[name]
            qty = Decimal(rnd.choice([1, 1, 1, 2])) if m.unit == "trolley" else Decimal(rnd.choice([20, 40, 60] if m.unit == "bag" else [200, 400, 500]))  # fmt: skip
            veh = rnd.choice(fleet)
            drv = next(d for d in drivers if d.default_vehicle_id == veh.id)
            loose = m.unit == "trolley"
            load_unit = "dumper" if loose and veh.type == "dumper" else None
            half = loose and rnd.random() < 0.15
            if load_unit:
                qty = Decimal(1)
            # some sand trolleys also carry cement bags on top
            extra = materials["Cement"] if name == "Rait (Sand)" and not load_unit and rnd.random() < 0.2 else None
            extra_qty = Decimal(10) if extra else None
            # a half trolley is often shared: half one material, half another
            if half and not load_unit and rnd.random() < 0.5:
                extra = materials[rnd.choice([n for n in ("Rait (Sand)", "Bajri (Gravel)", "Crush") if n != name])]
                extra_qty = qty * Decimal("0.5")
            stock_qty = qty * (m.dumper_qty if load_unit else 1)
            if db.get(StockItem, m.id).qty_on_hand < stock_qty:
                restock(day, name, 40 if loose else 400)
            if extra and db.get(StockItem, extra.id).qty_on_hand < extra_qty:
                restock(day, extra.name, 40 if extra.unit == "trolley" else 400)
            d = deliveries.create(db, DeliveryIn(
                date=day, customer_id=cust.id, site_id=rnd.choice(sites[cust.id]).id, material_id=m.id, qty=qty,
                load_unit=load_unit, load_size="half" if half else "full",
                freight_amount=Decimal(rnd.choice([0, 500, 800, 1000, 1500])), vehicle_id=veh.id, driver_id=drv.id,
                extra_material_id=extra.id if extra else None, extra_qty=extra_qty,
            ))[0]  # fmt: skip
            if cust is cash_customer:  # pays on the spot, as the challan screen's "Paid in full" does
                receipt, _ = payments.create(db, PaymentIn(
                    date=day, direction="in", party_id=cust.id, mode="cash", money_account_id=cash.id,
                    amount=d.sale_amount + d.freight_amount + d.extra_amount, notes=f"Paid with challan {d.challan_no}",
                ))  # fmt: skip
                d.receipt_id = receipt.id
            elif cust is advance_customer and balance_of(db, cust.account_id) > -30000 and offset < DAYS - 4:
                # tops up whenever the advance runs low, except the last few days so the demo shows a low advance
                payments.create(db, PaymentIn(
                    date=day, direction="in", party_id=cust.id, mode="bank", money_account_id=bank.id,
                    amount=Decimal(150000), notes="Advance top-up",
                ))  # fmt: skip
        if rnd.random() < 0.35:
            rentals.create(db, RentalIn(
                date=day, customer_id=rnd.choice([c for c in customers if c is not cash_customer]).id,
                vehicle_id=(ld := rnd.choice(loaders)).id,
                operator_id=next(o for o in operators if o.default_vehicle_id == ld.id).id, basis="hour",
                qty=Decimal(rnd.choice([3, 4, 6, 8])), rate=Decimal(1200),
            ))  # fmt: skip
        for veh in rnd.sample(fleet + loaders, 3):  # diesel: half on pump credit, half cash
            on_credit = rnd.random() < 0.5
            litres = Decimal(rnd.randint(12, 28))
            expenses.create(db, ExpenseIn(
                date=day, category="diesel", vehicle_id=veh.id, amount=litres * 285, litres=litres,
                meter_reading=Decimal(rnd.randint(1000, 90000)),
                paid_via="party_credit" if on_credit else "money_account",
                party_id=pump.id if on_credit else None, money_account_id=None if on_credit else cash.id,
            ))  # fmt: skip
        if rnd.random() < 0.12:
            expenses.create(db, ExpenseIn(
                date=day, category=rnd.choice(["repair", "tyre", "toll", "office"]), vehicle_id=rnd.choice(fleet).id,
                amount=Decimal(rnd.randint(8, 60) * 100), paid_via="money_account", money_account_id=cash.id,
            ))  # fmt: skip
        labour.save_attendance(db, [
            AttendanceIn(date=day, staff_id=w.id, status=rnd.choices(["present", "half", "absent"], [88, 6, 6])[0],
                         overtime_hours=Decimal(rnd.choice([0, 0, 0, 2])), vehicle_id=None)
            for w in labour_crew
        ])  # fmt: skip
        if day.weekday() == 4:  # Friday: customers pay most of what they owe, we pay suppliers
            for cust in customers:
                if cust in (cash_customer, advance_customer) or (cust is slow_payer and offset > DAYS - 21):
                    continue
                owed = balance_of(db, cust.account_id)
                if owed < 5000 or rnd.random() < 0.15:
                    continue
                amount = (owed * Decimal(rnd.randint(55, 95)) / 100 // 500) * 500
                mode = rnd.choice(["cash", "bank", "cheque"])
                payments.create(db, PaymentIn(
                    date=day, direction="in", party_id=cust.id, mode=mode,
                    money_account_id=(cash if mode == "cash" else bank).id, amount=amount,
                    ref_no=f"CHQ-{rnd.randint(100000, 999999)}" if mode == "cheque" else None,
                ))  # fmt: skip
            for sup in (suppliers["Crusher X"], suppliers["Al-Fazal Bhatta"], suppliers["Bestway Cement Dealer"]):
                owed = -balance_of(db, sup.account_id)
                if owed >= 10000:
                    payments.create(db, PaymentIn(
                        date=day, direction="out", party_id=sup.id, mode="bank", money_account_id=bank.id,
                        amount=(owed * Decimal(rnd.randint(60, 90)) / 100 // 1000) * 1000,
                    ))  # fmt: skip
            owed_pump = -balance_of(db, pump.account_id)
            if owed_pump >= 5000:
                payments.create(db, PaymentIn(
                    date=day, direction="out", party_id=pump.id, mode="cash", money_account_id=cash.id,
                    amount=(owed_pump * Decimal("0.8") // 500) * 500,
                ))  # fmt: skip
            payments.create(db, PaymentIn(
                date=day, direction="out", staff_id=rnd.choice(drivers).id, purpose="advance", mode="cash",
                money_account_id=cash.id, amount=Decimal(rnd.choice([2000, 3000, 5000])),
            ))  # fmt: skip
        if day.weekday() == 5:  # Saturday: daily-wage labour is paid what they earned that week
            for w in labour_crew:
                due = -balance_of(db, w.account_id)
                if due > 0:
                    payments.create(db, PaymentIn(
                        date=day, direction="out", staff_id=w.id, purpose="salary", mode="cash",
                        money_account_id=cash.id, amount=due,
                    ))  # fmt: skip
        if (day + dt.timedelta(days=1)).day == 1:
            month_ends.add(day)
        db.commit()

    # leave the advance customer with a little advance, so the reminders have something to show
    owed = balance_of(db, advance_customer.account_id)
    if owed > -3000:
        payments.create(db, PaymentIn(
            date=today, direction="in", party_id=advance_customer.id, mode="cash", money_account_id=cash.id,
            amount=owed + 3000, notes="Advance top-up",
        ))  # fmt: skip
    db.commit()

    # ---- settlements, a bill, a count -----------------------------------------------------------
    for end in sorted(month_ends):
        start = end.replace(day=1)
        for s in [*drivers, *operators, helper]:
            labour.create_settlement(db, SettlementIn(staff_id=s.id, period_from=max(start, cutover), period_to=end))
    for end in sorted(month_ends):  # salaries are paid from the bank once settled
        for s in [*drivers, *operators, helper]:
            due = -balance_of(db, s.account_id)
            if due > 0:
                payments.create(db, PaymentIn(
                    date=end, direction="out", staff_id=s.id, purpose="salary", mode="bank",
                    money_account_id=bank.id, amount=due,
                ))  # fmt: skip
    cust = customers[0]
    d_list, r_list = invoices.uninvoiced(db, cust.id, cutover, today, None)
    if d_list:
        invoices.create(db, InvoiceIn(
            date=today, customer_id=cust.id, period_from=cutover, period_to=today, is_tax_invoice=True,
            tax_rate=Decimal("5"), delivery_ids=[d.id for d in d_list[:25]], rental_ids=[r.id for r in r_list[:5]],
        ))  # fmt: skip
    stock.record_count(db, date=today, material_id=materials["Rait (Sand)"].id,
                       physical_qty=db.get(StockItem, materials["Rait (Sand)"].id).qty_on_hand - Decimal("0.5"))  # fmt: skip
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first (dev only)")
    args = parser.parse_args()
    if get_settings().env == "prod":
        raise SystemExit("Refusing to seed demo data with ENV=prod")
    install_audit_hooks()
    if args.reset:
        if engine.dialect.name == "postgresql":
            with engine.begin() as conn:
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
        else:
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        # Tables now match the models, so mark the DB as migrated; otherwise the next `alembic upgrade` fails.
        from alembic import command
        from alembic.config import Config

        command.stamp(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    elif get_settings().auto_create_tables:
        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        bootstrap(db)
        if db.scalar(select(func.count()).select_from(Staff)) or db.scalar(select(func.count()).select_from(Vehicle)):
            raise SystemExit("Database already has data. Use --reset on a dev database.")
        run(db)
        from app.accounting.service import trial_balance

        tb = trial_balance(db, None)
        inv = db.scalar(select(Account.id).where(Account.code == "1100"))
        stock_value = db.scalar(select(func.sum(StockItem.value))) or 0
        print(f"Seeded {DAYS} days. Trial balance balanced: {tb.balanced} (Dr {tb.total_debit} = Cr {tb.total_credit})")
        print(f"Inventory ledger {balance_of(db, inv)} == stock value {stock_value}")
        print(
            f"Materials: {db.scalar(select(func.count()).select_from(Material))}; logins: admin/admin12345, munshi/munshi12345"
        )


if __name__ == "__main__":
    main()
