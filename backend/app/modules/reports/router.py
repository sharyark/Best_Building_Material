import datetime as dt
import re
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.deps import DB, require_perm
from app.modules.common import get_or_404
from app.modules.masters.models import Party
from app.modules.reports import queries as q
from app.modules.reports.export import respond
from app.modules.reports.table import fmt_date, fmt_money

router = APIRouter(prefix="/reports", tags=["reports"])

Format = Annotated[Literal["json", "xlsx", "pdf"], Query(alias="format")]
DateFrom = Annotated[dt.date | None, Query(alias="from")]
DateTo = Annotated[dt.date | None, Query(alias="to")]


def perm(name: str):
    return Depends(require_perm(name))


@router.get("/dashboard", dependencies=[perm("dashboard.view")])
def dashboard(db: DB):
    return JSONResponse(q.dashboard(db))


@router.get("/khata/{party_id}", dependencies=[perm("report.khata")])
def khata(party_id: int, db: DB, date_from: DateFrom = None, date_to: DateTo = None, fmt: Format = "json"):
    """Customer or supplier statement: date-wise Dr/Cr with running balance."""
    start, end = q.default_range(date_from, date_to)
    if date_from is None:
        start = dt.date(2000, 1, 1)  # a khata defaults to the whole history
    return respond(q.party_khata(db, party_id, start, end), fmt)


@router.get("/khata/{party_id}/share", dependencies=[perm("report.khata")])
def khata_share(party_id: int, db: DB, date_from: DateFrom = None, date_to: DateTo = None):
    """WhatsApp share link. No API needed: wa.me opens the user's own WhatsApp with the text filled in."""
    party = get_or_404(db, Party, party_id, "Party")
    start, end = q.default_range(date_from, date_to)
    if date_from is None:
        start = dt.date(2000, 1, 1)
    table = q.party_khata(db, party_id, start, end)
    closing = table.meta["closing"]
    side = "receivable from you" if closing > 0 else "payable to you" if closing < 0 else "settled"
    last = [r for r in table.rows if r["type"] != "Opening"][-5:]
    lines = [
        f"{fmt_date(r['date'])} {r['type']}: {fmt_money(r['debit'] or r['credit'])} {'Dr' if r['debit'] else 'Cr'}"
        for r in last
    ]
    message = (
        f"Assalam o Alaikum {party.name},\nYour account statement as of {end:%d-%m-%Y}:\n"
        + ("\n".join(lines) + "\n" if lines else "")
        + f"Balance: {fmt_money(abs(closing))} ({side})."
    )
    digits = re.sub(r"\D", "", party.phone or "")
    url = f"https://wa.me/{digits}?text={quote(message)}" if digits else f"https://wa.me/?text={quote(message)}"
    return {"message": message, "url": url, "has_phone": bool(digits)}


@router.get("/staff-khata/{staff_id}", dependencies=[perm("report.labour_khata")])
def staff_khata(staff_id: int, db: DB, date_from: DateFrom = None, date_to: DateTo = None, fmt: Format = "json"):
    start, end = q.default_range(date_from, date_to)
    return respond(q.staff_khata(db, staff_id, start, end), fmt)


@router.get("/outstanding", dependencies=[perm("report.outstanding")])
def outstanding(
    db: DB,
    as_of: dt.date | None = None,
    kind: Literal["receivable", "payable"] = "receivable",
    fmt: Format = "json",
):
    return respond(q.outstanding(db, as_of or dt.date.today(), kind), fmt)


@router.get("/cash-book", dependencies=[perm("report.cashbook")])
def cash_book(
    db: DB,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    money_account_id: int | None = None,
    fmt: Format = "json",
):
    start, end = q.default_range(date_from, date_to)
    return respond(q.cash_book(db, money_account_id, start, end), fmt)


@router.get("/day-book", dependencies=[perm("report.daybook")])
def day_book(db: DB, date: dt.date | None = None, fmt: Format = "json"):
    return respond(q.day_book(db, date or dt.date.today()), fmt)


@router.get("/vehicle-pnl", dependencies=[perm("report.profit")])
def vehicle_pnl(db: DB, date_from: DateFrom = None, date_to: DateTo = None, fmt: Format = "json"):
    start, end = q.default_range(date_from, date_to)
    return respond(q.vehicle_pnl(db, start, end), fmt)


@router.get("/material-margin", dependencies=[perm("report.profit")])
def material_margin(db: DB, date_from: DateFrom = None, date_to: DateTo = None, fmt: Format = "json"):
    start, end = q.default_range(date_from, date_to)
    return respond(q.material_margin(db, start, end), fmt)


@router.get("/labour-cost", dependencies=[perm("report.profit")])
def labour_cost(
    db: DB,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    group_by: Literal["month", "week", "vehicle", "site", "staff"] = "month",
    fmt: Format = "json",
):
    start, end = q.default_range(date_from, date_to)
    return respond(q.labour_cost(db, start, end, group_by), fmt)


@router.get("/rental-income", dependencies=[perm("report.profit")])
def rental_income(
    db: DB,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    group_by: Literal["vehicle", "customer"] = "vehicle",
    fmt: Format = "json",
):
    start, end = q.default_range(date_from, date_to)
    return respond(q.rental_income(db, start, end, group_by), fmt)


@router.get("/profit-loss", dependencies=[perm("report.profit")])
def profit_loss(db: DB, date_from: DateFrom = None, date_to: DateTo = None, fmt: Format = "json"):
    start, end = q.default_range(date_from, date_to)
    return respond(q.monthly_pnl(db, start, end), fmt)


@router.get("/yard-stock", dependencies=[perm("report.stock")])
def yard_stock(db: DB, date_from: DateFrom = None, date_to: DateTo = None, fmt: Format = "json"):
    start, end = q.default_range(date_from, date_to)
    return respond(q.yard_stock(db, start, end), fmt)
