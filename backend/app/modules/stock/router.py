from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.accounting.posting import ensure_period_open
from app.core.deps import DB, require_perm
from app.modules.masters.models import Material
from app.modules.stock import schemas as s
from app.modules.stock import service
from app.modules.stock.models import StockCount, StockItem, StockMove

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("", response_model=list[s.StockItemOut], dependencies=[Depends(require_perm("stock.view"))])
def yard_stock(db: DB):
    """Live yard balance for every active material (zero rows included)."""
    items = {i.material_id: i for i in db.scalars(select(StockItem))}
    out = []
    for m in db.scalars(select(Material).where(Material.is_active).order_by(Material.name)):
        item = items.get(m.id)
        out.append(
            s.StockItemOut(
                material_id=m.id,
                material_name=m.name,
                unit=m.unit,
                qty_on_hand=item.qty_on_hand if item else 0,
                avg_cost=item.avg_cost if item else 0,
                value=item.value if item else 0,
            )
        )
    return out


@router.get("/counts", response_model=list[s.StockCountOut], dependencies=[Depends(require_perm("stock.view"))])
def list_counts(db: DB):
    return db.scalars(select(StockCount).order_by(StockCount.date.desc(), StockCount.id.desc()).limit(200)).all()


@router.post(
    "/counts", response_model=s.StockCountOut, status_code=201, dependencies=[Depends(require_perm("stock.count"))]
)
def physical_count(data: s.StockCountIn, db: DB):
    ensure_period_open(db, data.date)
    count = service.record_count(db, date=data.date, material_id=data.material_id, physical_qty=data.physical_qty)
    db.commit()
    return count


@router.post("/opening", status_code=204, dependencies=[Depends(require_perm("opening.write"))])
def opening_stock(data: list[s.OpeningStockIn], db: DB):
    """One screen: physical count of yard stock with rates, posted against Opening Balance Equity."""
    for row in data:
        ensure_period_open(db, row.date)
        service.set_opening_stock(db, date=row.date, material_id=row.material_id, qty=row.qty, rate=row.rate)
    db.commit()


@router.get("/opening", response_model=list[s.OpeningStockOut], dependencies=[Depends(require_perm("opening.write"))])
def list_opening_stock(db: DB):
    """Currently active opening stock rows (so the opening screen can show what was already entered)."""
    reversed_ids = select(StockMove.reverses_id).where(StockMove.reverses_id.is_not(None))
    moves = db.scalars(
        select(StockMove).where(
            StockMove.source_type == "opening", StockMove.reverses_id.is_(None), StockMove.id.not_in(reversed_ids)
        )
    ).all()
    return [s.OpeningStockOut(material_id=m.material_id, date=m.date, qty=m.qty_in, rate=m.rate) for m in moves]
