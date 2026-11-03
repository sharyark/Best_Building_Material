"""A tiny demo: one of everything and one week of entries, small enough to follow by hand.

`python -m app.seed --reset --small`. MANUAL.md walks through these same entries and their numbers.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting.schemas import OpeningBalanceIn
from app.accounting.service import set_opening_balance
from app.audit.hooks import set_actor
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.deliveries import service as deliveries
from app.modules.deliveries.schemas import ChallanPaymentIn, DeliveryIn
from app.modules.expenses import service as expenses
from app.modules.expenses.schemas import ExpenseIn
from app.modules.labour import service as labour
from app.modules.labour.schemas import AttendanceIn
from app.modules.masters import service as masters
from app.modules.masters.models import MoneyAccount
from app.modules.masters.schemas import MaterialIn, PartyIn, SiteIn, StaffIn, VehicleIn
from app.modules.payments import service as payments
from app.modules.payments.schemas import PaymentIn
from app.modules.purchases import service as purchases
from app.modules.purchases.schemas import PurchaseIn, PurchaseLineIn
from app.modules.stock import service as stock

D = Decimal


def run_small(db: Session) -> None:
    today = dt.date.today()
    day0 = today - dt.timedelta(days=5)  # the day the shop moved from the paper register

    def day(n: int) -> dt.date:
        return day0 + dt.timedelta(days=n)

    admin = db.scalar(select(User).where(User.role == "admin"))
    set_actor(db, admin.id)
    if not db.scalar(select(User.id).where(User.phone == "munshi")):
        db.add(User(name="Munshi", phone="munshi", password_hash=hash_password("munshi12345"), role="accountant"))

    # ---- Masters: one of everything ---------------------------------------------------------------
    cash = db.scalar(select(MoneyAccount).where(MoneyAccount.name == "Cash in Hand"))
    rait = masters.create_material(
        db, MaterialIn(name="Rait (Sand)", unit="trolley", default_sale_rate=D(3300), default_purchase_rate=D(2000))
    )
    customer = masters.create_party(db, PartyIn(type="customer", name="Ali Builders", phone="0300-1112233"))
    site = masters.create_site(db, SiteIn(party_id=customer.id, name="Plot 12"))
    supplier = masters.create_party(db, PartyIn(type="supplier", name="Crusher X", phone="0301-2223344"))
    tractor = masters.create_vehicle(db, VehicleIn(type="tractor_trolley", name="Tractor-1", reg_no="LEA-1001"))
    driver = masters.create_staff(
        db,
        StaffIn(
            name="Aslam", role="driver", wage_type="monthly", wage_amount=D(15000), trip_rate=D(200),
            default_vehicle_id=tractor.id,
        ),
    )  # fmt: skip
    labourer = masters.create_staff(db, StaffIn(name="Raju", role="labour", wage_type="daily", wage_amount=D(900)))
    db.flush()

    # ---- Day 0: opening balances from the old register ----------------------------------------------
    for kind, ref, side, amount in (
        ("money_account", cash.id, "dr", 50000),  # cash in the galla
        ("party", customer.id, "dr", 20000),  # Ali Builders still owes from the register
        ("party", supplier.id, "cr", 10000),  # we still owe Crusher X
    ):
        set_opening_balance(db, OpeningBalanceIn(date=day0, kind=kind, ref_id=ref, side=side, amount=D(amount)))
    stock.set_opening_stock(db, date=day0, material_id=rait.id, qty=D(5), rate=D(2000))  # 5 trolleys in the yard

    # ---- Day 1: sand bought on credit; Raju works -----------------------------------------------------
    purchases.create(db, PurchaseIn(
        date=day(1), supplier_id=supplier.id, transport_by="supplier",
        lines=[PurchaseLineIn(material_id=rait.id, qty=D(10), rate=D(2000))],
    ))  # fmt: skip
    labour.save_attendance(db, [AttendanceIn(date=day(1), staff_id=labourer.id, status="present")])

    # ---- Day 2: 3 trolleys on udhaar; diesel; Raju works ----------------------------------------------
    deliveries.create(db, DeliveryIn(
        date=day(2), customer_id=customer.id, site_id=site.id, material_id=rait.id, qty=D(3), sale_rate=D(3300),
        vehicle_id=tractor.id, driver_id=driver.id,
    ))  # fmt: skip
    expenses.create(db, ExpenseIn(
        date=day(2), category="diesel", vehicle_id=tractor.id, litres=D(10), rate_per_litre=D(300),  # = 3,000
        paid_via="money_account", money_account_id=cash.id,
    ))  # fmt: skip
    labour.save_attendance(db, [AttendanceIn(date=day(2), staff_id=labourer.id, status="present")])

    # ---- Day 3: 2 trolleys paid in cash on the spot; Aslam takes an advance ---------------------------
    deliveries.create(db, DeliveryIn(
        date=day(3), customer_id=customer.id, site_id=site.id, material_id=rait.id, qty=D(2), sale_rate=D(3300),
        vehicle_id=tractor.id, driver_id=driver.id,
        payment=ChallanPaymentIn(amount=D(6600), money_account_id=cash.id, mode="cash"),
    ))  # fmt: skip
    payments.create(db, PaymentIn(
        date=day(3), direction="out", staff_id=driver.id, purpose="advance", money_account_id=cash.id,
        mode="cash", amount=D(5000),
    ))  # fmt: skip

    # ---- Day 4: Ali Builders pays part of the udhaar; we pay Crusher X -------------------------------
    payments.create(db, PaymentIn(
        date=day(4), direction="in", party_id=customer.id, money_account_id=cash.id, mode="cash", amount=D(15000),
    ))  # fmt: skip
    payments.create(db, PaymentIn(
        date=day(4), direction="out", party_id=supplier.id, money_account_id=cash.id, mode="cash", amount=D(20000),
    ))  # fmt: skip

    # ---- Day 5 (today): the week's trip money to Aslam; Raju's two days' wages --------------------
    payments.create(db, PaymentIn(
        date=day(5), direction="out", staff_id=driver.id, purpose="trip", money_account_id=cash.id,
        mode="cash", amount=D(1000),
    ))  # fmt: skip
    payments.create(db, PaymentIn(
        date=day(5), direction="out", staff_id=labourer.id, purpose="salary", money_account_id=cash.id,
        mode="cash", amount=D(1800),
    ))  # fmt: skip
    db.commit()
