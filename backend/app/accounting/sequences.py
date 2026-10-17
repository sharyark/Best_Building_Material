"""Gap-free document numbers per type and financial year."""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.accounting.models import DocSequence
from app.core.config import get_settings

PREFIX = {
    "challan": "CH",
    "purchase": "PB",
    "rental": "RN",
    "invoice": "INV",
    "receipt": "RV",
    "payment": "PV",
    "expense": "EV",
}


def fin_year_label(day: dt.date) -> str:
    start = get_settings().fin_year_start_month
    if start == 1:
        return str(day.year)
    year = day.year if day.month >= start else day.year - 1
    return f"{year}-{(year + 1) % 100:02d}"


def next_doc_no(db: Session, doc_type: str, day: dt.date) -> str:
    """Runs inside the caller's transaction: a rollback also rolls back the number (no gaps)."""
    fy = fin_year_label(day)
    query = select(DocSequence).where(DocSequence.doc_type == doc_type, DocSequence.fin_year == fy)
    seq = db.execute(query.with_for_update()).scalar_one_or_none()
    if seq is None:
        try:
            with db.begin_nested():
                db.add(DocSequence(doc_type=doc_type, fin_year=fy, last_no=0))
        except IntegrityError:
            pass  # another request created it first
        seq = db.execute(query.with_for_update()).scalar_one()
    seq.last_no += 1
    db.flush()
    return f"{PREFIX[doc_type]}/{fy}/{seq.last_no:05d}"
