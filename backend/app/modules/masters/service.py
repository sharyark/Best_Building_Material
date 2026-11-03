import datetime as dt
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting.balances import account_balances, balance_of, oldest_unpaid_dates
from app.accounting.chart import Code, create_sub_account
from app.accounting.models import Account
from app.core.config import get_settings
from app.core.errors import Conflict, DomainError, NotFound
from app.core.money import money
from app.modules.masters.models import Material, MoneyAccount, Party, RateCard, Site, Staff, Vehicle
from app.modules.masters.schemas import (
    DriverSuggestion,
    MaterialIn,
    MoneyAccountIn,
    PartyBalance,
    PartyIn,
    RateCardIn,
    RateLookup,
    SiteIn,
    StaffIn,
    VehicleIn,
)


def create_party(db: Session, data: PartyIn) -> Party:
    party = Party(**data.model_dump())
    db.add(party)
    db.flush()
    is_supplier_only = party.type == "supplier"
    account = create_sub_account(
        db,
        prefix="P",
        ref_id=party.id,
        name=party.name,
        parent_code=Code.PAYABLES if is_supplier_only else Code.RECEIVABLES,
        type_="liability" if is_supplier_only else "asset",
    )
    party.account_id = account.id
    return party


def update_party(db: Session, party: Party, changes: dict) -> Party:
    for key, value in changes.items():
        setattr(party, key, value)
    if "name" in changes and party.account_id:
        db.get(Account, party.account_id).name = party.name
    db.flush()
    return party


def create_staff(db: Session, data: StaffIn) -> Staff:
    staff = Staff(**data.model_dump())
    _ensure_vehicle_free(db, staff)
    db.add(staff)
    db.flush()
    account = create_sub_account(
        db, prefix="S", ref_id=staff.id, name=staff.name, parent_code=Code.STAFF_PAYABLE, type_="liability"
    )
    staff.account_id = account.id
    return staff


def update_staff(db: Session, staff: Staff, changes: dict) -> Staff:
    for key, value in changes.items():
        setattr(staff, key, value)
    _ensure_vehicle_free(db, staff)
    if "name" in changes and staff.account_id:
        db.get(Account, staff.account_id).name = staff.name
    db.flush()
    return staff


def create_money_account(db: Session, data: MoneyAccountIn) -> MoneyAccount:
    money_account = MoneyAccount(**data.model_dump())
    db.add(money_account)
    db.flush()
    account = create_sub_account(
        db, prefix="M", ref_id=money_account.id, name=money_account.name, parent_code=Code.CASH_BANK, type_="asset"
    )
    money_account.account_id = account.id
    return money_account


def update_money_account(db: Session, money_account: MoneyAccount, changes: dict) -> MoneyAccount:
    for key, value in changes.items():
        setattr(money_account, key, value)
    if "name" in changes and money_account.account_id:
        db.get(Account, money_account.account_id).name = money_account.name
    db.flush()
    return money_account


def create_site(db: Session, data: SiteIn) -> Site:
    party = db.get(Party, data.party_id)
    if party is None or party.type == "supplier":
        raise NotFound("Customer not found for this site")
    site = Site(**data.model_dump())
    db.add(site)
    db.flush()
    return site


def create_material(db: Session, data: MaterialIn) -> Material:
    if db.scalar(select(Material.id).where(Material.name == data.name)):
        raise Conflict("A material with this name already exists", code="DUPLICATE")
    material = Material(**data.model_dump())
    db.add(material)
    db.flush()
    return material


def create_vehicle(db: Session, data: VehicleIn) -> Vehicle:
    if db.scalar(select(Vehicle.id).where(Vehicle.name == data.name)):
        raise Conflict("A vehicle with this name already exists", code="DUPLICATE")
    vehicle = Vehicle(**data.model_dump())
    db.add(vehicle)
    db.flush()
    return vehicle


def upsert_rate_card(db: Session, data: RateCardIn) -> RateCard:
    existing = db.scalar(
        select(RateCard).where(
            RateCard.party_id == data.party_id,
            RateCard.material_id == data.material_id,
            RateCard.effective_from == data.effective_from,
        )
    )
    if existing:
        existing.rate = data.rate
        db.flush()
        return existing
    card = RateCard(**data.model_dump())
    db.add(card)
    db.flush()
    return card


def party_balance(db: Session, party: Party, today: dt.date) -> PartyBalance:
    settings = get_settings()
    balance = balance_of(db, party.account_id) if party.account_id else Decimal(0)
    oldest = oldest_unpaid_dates(db, [party.account_id]).get(party.account_id) if balance > 0 else None
    return PartyBalance(
        party_id=party.id,
        balance=money(balance),
        oldest_unpaid_date=oldest,
        days_unpaid=(today - oldest).days if oldest else None,
        advance_low_threshold=settings.advance_low_threshold,
        credit_overdue_days=settings.credit_overdue_days,
    )


def load_factor(material: Material, load_unit: str | None) -> Decimal:
    """How much stock (in the material's unit) one full load takes out of the yard."""
    if load_unit is None:
        return Decimal(1)
    factor = material.dumper_qty if load_unit == "dumper" else material.bucket_qty
    if not factor:
        what = "dumper" if load_unit == "dumper" else "loader bucket"
        raise DomainError(
            f"{material.name} has no {what} size yet. Set how much one {what} holds in Masters > Materials.",
            code="LOAD_SIZE_MISSING",
            details={"material_id": material.id, "load_unit": load_unit},
        )
    return factor


def lookup_sale_rate(
    db: Session, party_id: int, material_id: int, on: dt.date, load_unit: str | None = None
) -> RateLookup:
    if load_unit is not None:
        material = db.get(Material, material_id)
        if material is None:
            raise NotFound("Material not found")
        fixed = material.dumper_rate if load_unit == "dumper" else material.bucket_rate
        if fixed:
            return RateLookup(rate=fixed, source="default")
        # No separate load rate: scale the per-unit rate (customer's card first) by the load size.
        base = lookup_sale_rate(db, party_id, material_id, on)
        return RateLookup(rate=money(base.rate * load_factor(material, load_unit)), source=base.source)
    card = db.scalar(
        select(RateCard)
        .where(RateCard.party_id == party_id, RateCard.material_id == material_id, RateCard.effective_from <= on)
        .order_by(RateCard.effective_from.desc())
        .limit(1)
    )
    if card:
        return RateLookup(rate=card.rate, source="rate_card")
    material = db.get(Material, material_id)
    if material is None:
        raise NotFound("Material not found")
    return RateLookup(rate=material.default_sale_rate, source="default")


def attach_balances(db: Session, rows: list, out_items: list) -> None:
    balances = account_balances(db, [r.account_id for r in rows if r.account_id])
    for row, out in zip(rows, out_items, strict=True):
        out.balance = balances.get(row.account_id, Decimal("0")) if row.account_id else Decimal("0")


DRIVING_ROLES = ("driver", "operator")


def _ensure_vehicle_free(db: Session, staff: Staff) -> None:
    """One driver per vehicle: the link is set only here in Masters, and documents follow it."""
    # is_active is still None on a new, unflushed row (the column default applies on insert).
    if not (staff.default_vehicle_id and staff.is_active is not False and staff.role in DRIVING_ROLES):
        return
    query = select(Staff).where(
        Staff.default_vehicle_id == staff.default_vehicle_id, Staff.is_active, Staff.role.in_(DRIVING_ROLES)
    )
    if staff.id is not None:
        query = query.where(Staff.id != staff.id)
    other = db.scalars(query.limit(1)).first()
    if other is not None:
        vehicle = db.get(Vehicle, staff.default_vehicle_id)
        raise Conflict(
            f"{vehicle.name if vehicle else 'This vehicle'} already has driver {other.name}. "
            f"Remove {other.name} from it first.",
            code="VEHICLE_HAS_DRIVER",
            details={"vehicle_id": staff.default_vehicle_id, "driver_id": other.id},
        )


def _regular_driver(db: Session, vehicle_id: int) -> int | None:
    return db.scalar(
        select(Staff.id)
        .where(Staff.default_vehicle_id == vehicle_id, Staff.is_active, Staff.role.in_(DRIVING_ROLES))
        .order_by(Staff.id)
        .limit(1)
    )


def _free_drivers(db: Session) -> list[int]:
    """Active drivers not tied to any active vehicle: the only ones who may stand in on another vehicle."""
    return list(
        db.scalars(
            select(Staff.id)
            .outerjoin(Vehicle, Vehicle.id == Staff.default_vehicle_id)
            .where(Staff.is_active, Staff.role.in_(DRIVING_ROLES))
            .where((Staff.default_vehicle_id.is_(None)) | (Vehicle.is_active.is_(False)))
            .order_by(Staff.name)
        )
    )


def _absent_drivers(db: Session, on: dt.date) -> set[int]:
    from app.modules.labour.models import Attendance

    return set(
        db.scalars(
            select(Attendance.staff_id)
            .join(Staff, Staff.id == Attendance.staff_id)
            .where(Attendance.date == on, Attendance.status == "absent", Staff.role.in_(DRIVING_ROLES))
        )
    )


def usual_trip_rate(staff: Staff) -> Decimal:
    if staff.trip_rate:
        return staff.trip_rate
    return staff.wage_amount if staff.wage_type == "per_trip" else Decimal("0")


def trip_pay_for(
    db: Session, driver_id: int | None, given: Decimal | None, trips: int = 1
) -> tuple[Decimal, int | None]:
    """(amount, driver's ledger account). `given` None means trips x the driver's usual rate."""
    if driver_id is None:
        if given:
            raise DomainError("Pick the driver to give trip money to.", code="TRIP_PAY_NEEDS_DRIVER")
        return money(0), None
    staff = db.get(Staff, driver_id)
    if staff is None:
        raise NotFound("Driver not found")
    return money(given if given is not None else usual_trip_rate(staff) * trips), staff.account_id


def ensure_driver_allowed(db: Session, vehicle_id: int | None, driver_id: int | None, on: dt.date) -> None:
    """A vehicle with its own driver takes only that driver, unless he is absent that day; otherwise a
    free driver (one not linked to any vehicle). Services skip this when an edit keeps the saved pair."""
    if not vehicle_id or not driver_id:
        return
    regular = _regular_driver(db, vehicle_id)
    if driver_id == regular:
        return
    if regular is not None and regular not in _absent_drivers(db, on):
        name = db.get(Staff, regular).name
        raise DomainError(
            f"This vehicle's driver is {name}. To use someone else, change the driver in Masters first.",
            code="DRIVER_NOT_ALLOWED",
            details={"regular_driver_id": regular},
        )
    if driver_id not in _free_drivers(db):
        raise DomainError(
            "This driver is linked to another vehicle. Pick a free driver (one not linked to any vehicle).",
            code="DRIVER_NOT_ALLOWED",
        )


def suggest_driver(db: Session, vehicle_id: int, on: dt.date) -> DriverSuggestion:
    """Driver for a vehicle on a day, and who else may be picked.

    The vehicle's own driver is fixed. Only when it has none, or he is marked absent, may a free driver be
    picked; that pick then becomes "today's" driver for the vehicle's next entries without any extra step.
    """
    # Imported here: these modules import masters models, so a top-level import would be circular.
    from app.modules.deliveries.models import Delivery
    from app.modules.purchases.models import Purchase
    from app.modules.rentals.models import Rental

    if db.get(Vehicle, vehicle_id) is None:
        raise NotFound("Vehicle not found")
    absent = _absent_drivers(db, on)
    regular = _regular_driver(db, vehicle_id)
    regular_absent = regular is not None and regular in absent
    if regular is not None and not regular_absent:
        return DriverSuggestion(
            driver_id=regular, source="regular", locked=True, allowed_driver_ids=[regular],
            regular_driver_id=regular, regular_absent=False, absent_driver_ids=sorted(absent),
        )  # fmt: skip

    allowed = [d for d in _free_drivers(db) if d not in absent]
    latest: tuple[dt.datetime, int] | None = None
    for model, column in ((Delivery, Delivery.driver_id), (Purchase, Purchase.driver_id), (Rental, Rental.operator_id)):
        row = db.execute(
            select(model.updated_at, column)
            .where(model.vehicle_id == vehicle_id, model.date == on, model.status == "active", column.is_not(None))
            .order_by(model.updated_at.desc())
            .limit(1)
        ).first()
        if row and (latest is None or row[0] > latest[0]):
            latest = (row[0], row[1])
    today = latest[1] if latest and latest[1] in allowed else None
    return DriverSuggestion(
        driver_id=today,
        source="today" if today else None,
        locked=False,
        allowed_driver_ids=allowed,
        regular_driver_id=regular,
        regular_absent=regular_absent,
        absent_driver_ids=sorted(absent),
    )
