import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.core.types import MoneyIn, QtyIn


class StockItemOut(BaseModel):
    material_id: int
    material_name: str
    unit: str
    qty_on_hand: Decimal
    avg_cost: Decimal
    value: Decimal


class StockCountIn(BaseModel):
    date: dt.date
    material_id: int
    physical_qty: QtyIn


class StockCountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: dt.date
    material_id: int
    system_qty: Decimal
    physical_qty: Decimal
    diff: Decimal
    journal_id: int | None


class OpeningStockIn(BaseModel):
    date: dt.date
    material_id: int
    qty: QtyIn
    rate: MoneyIn


class OpeningStockOut(BaseModel):
    material_id: int
    date: dt.date
    qty: Decimal
    rate: Decimal
