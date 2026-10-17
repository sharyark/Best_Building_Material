"""Yard stock with moving weighted-average cost.

new_avg = (old_qty*old_avg + in_qty*in_rate) / (old_qty + in_qty). `value` is tracked alongside qty so the
stock value always equals the Inventory account in the journal.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounting import rules
from app.accounting.chart import Chart
from app.accounting.posting import active_entries, post, reverse
from app.core.db import ZERO
from app.core.errors import InsufficientStock, NotFound
from app.core.money import money, rate4
from app.core.money import qty as q3
from app.modules.masters.models import Material
from app.modules.stock.models import StockCount, StockItem, StockMove


def get_item(db: Session, material_id: int, *, lock: bool = True) -> StockItem:
    stmt = select(StockItem).where(StockItem.material_id == material_id)
    item = db.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
    if item is None:
        if db.get(Material, material_id) is None:
            raise NotFound(f"Material {material_id} not found")
        item = StockItem(material_id=material_id, qty_on_hand=ZERO, avg_cost=ZERO, value=ZERO)
        db.add(item)
        db.flush()
    return item


def _refresh_avg(item: StockItem) -> None:
    if item.qty_on_hand > 0:
        item.avg_cost = rate4(item.value / item.qty_on_hand)


def receive(
    db: Session, *, date: dt.date, material_id: int, qty: Decimal, rate: Decimal, source_type: str, source_id: int
) -> StockMove:
    item = get_item(db, material_id)
    value = money(qty * rate)
    item.qty_on_hand = q3(item.qty_on_hand + qty)
    item.value = money(item.value + value)
    _refresh_avg(item)
    move = StockMove(
        date=date, material_id=material_id, qty_in=qty, rate=rate4(rate), value=value,
        source_type=source_type, source_id=source_id,
    )  # fmt: skip
    db.add(move)
    db.flush()
    return move


def issue(
    db: Session,
    *,
    date: dt.date,
    material_id: int,
    qty: Decimal,
    source_type: str,
    source_id: int,
    allow_negative: bool = False,
) -> tuple[StockMove, Decimal, Decimal]:
    """Take stock out at the current average. Returns (move, cost_rate, cost_amount)."""
    item = get_item(db, material_id)
    if not allow_negative and item.qty_on_hand < qty:
        raise InsufficientStock(
            f"Only {item.qty_on_hand} in yard, trying to issue {qty}",
            details={"available": str(item.qty_on_hand), "requested": str(qty), "material_id": material_id},
        )
    cost_rate = item.avg_cost
    cost_amount = item.value if qty == item.qty_on_hand else money(qty * cost_rate)
    item.qty_on_hand = q3(item.qty_on_hand - qty)
    item.value = money(item.value - cost_amount)
    move = StockMove(
        date=date, material_id=material_id, qty_out=qty, rate=cost_rate, value=-cost_amount,
        source_type=source_type, source_id=source_id,
    )  # fmt: skip
    db.add(move)
    db.flush()
    return move, cost_rate, cost_amount


def reverse_source(db: Session, source_type: str, source_id: int, *, allow_negative: bool = False) -> None:
    """Undo every not-yet-reversed move of a document by posting negated moves."""
    reversed_ids = select(StockMove.reverses_id).where(StockMove.reverses_id.is_not(None))
    moves = db.scalars(
        select(StockMove).where(
            StockMove.source_type == source_type,
            StockMove.source_id == source_id,
            StockMove.reverses_id.is_(None),
            StockMove.id.not_in(reversed_ids),
        )
    ).all()
    for move in moves:
        item = get_item(db, move.material_id)
        new_qty = q3(item.qty_on_hand - move.qty_in + move.qty_out)
        if new_qty < 0 and not allow_negative:
            raise InsufficientStock(
                "Cannot undo this: material from it has already been sold or issued",
                details={"material_id": move.material_id, "would_be": str(new_qty)},
            )
        item.qty_on_hand = new_qty
        item.value = money(item.value - move.value)
        _refresh_avg(item)
        db.add(
            StockMove(
                date=move.date,
                material_id=move.material_id,
                qty_in=-move.qty_in,
                qty_out=-move.qty_out,
                rate=move.rate,
                value=-move.value,
                source_type=move.source_type,
                source_id=move.source_id,
                reverses_id=move.id,
            )  # fmt: skip
        )
    db.flush()


def qty_as_of(db: Session, material_id: int, day: dt.date) -> Decimal:
    total = db.scalar(
        select(func.sum(StockMove.qty_in - StockMove.qty_out)).where(
            StockMove.material_id == material_id, StockMove.date <= day
        )
    )
    return q3(total or 0)


def record_count(db: Session, *, date: dt.date, material_id: int, physical_qty: Decimal) -> StockCount:
    """Physical count -> adjustment move at average cost, difference posted to Stock Loss."""
    item = get_item(db, material_id)
    system_qty = qty_as_of(db, material_id, date)
    diff = q3(physical_qty - system_qty)
    count = StockCount(date=date, material_id=material_id, system_qty=system_qty, physical_qty=physical_qty, diff=diff)
    db.add(count)
    db.flush()
    if diff != 0:
        value = money(abs(diff) * item.avg_cost)
        signed = value if diff > 0 else -value
        item.qty_on_hand = q3(item.qty_on_hand + diff)
        item.value = money(item.value + signed)
        db.add(
            StockMove(
                date=date,
                material_id=material_id,
                qty_in=max(diff, ZERO),
                qty_out=max(-diff, ZERO),
                rate=item.avg_cost,
                value=signed,
                source_type="adjustment",
                source_id=count.id,
            )  # fmt: skip
        )
        entry = post(
            db,
            date=date,
            source_type="stock_adjustment",
            source_id=count.id,
            narration=f"Stock count adjustment ({'+' if diff > 0 else ''}{diff})",
            lines=rules.stock_adjustment(Chart(db), signed),
        )
        count.journal_id = entry.id
    db.flush()
    return count


def set_opening_stock(db: Session, *, date: dt.date, material_id: int, qty: Decimal, rate: Decimal) -> StockMove | None:
    """Opening yard stock at cut-over. Re-entering replaces the earlier opening for the material."""
    get_item(db, material_id)
    for entry in active_entries(db, "opening_stock", material_id):
        reverse(db, entry.id, reason="opening stock re-entered")
    reverse_source(db, "opening", material_id, allow_negative=True)
    if qty <= 0:
        return None
    move = receive(
        db, date=date, material_id=material_id, qty=qty, rate=rate, source_type="opening", source_id=material_id
    )
    post(
        db,
        date=date,
        source_type="opening_stock",
        source_id=material_id,
        narration="Opening yard stock",
        lines=rules.opening_stock(Chart(db), move.value),
    )
    return move
