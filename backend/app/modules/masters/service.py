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
