"""Properties that must hold no matter what the accountant does."""

from decimal import Decimal

from sqlalchemy import func, select

from app.accounting.balances import balance_of
from app.accounting.models import Account, JournalEntry, JournalLine
from app.accounting.service import trial_balance
from app.modules.stock.models import StockItem
from tests.conftest import TODAY
from tests.test_core_flow import challan, purchase


def assert_invariants(db):
    db.expire_all()
    tb = trial_balance(db, None)
    assert tb.balanced
    # every single journal entry balances on its own
    unbalanced = db.execute(
        select(JournalLine.journal_id)
        .group_by(JournalLine.journal_id)
        .having(func.sum(JournalLine.debit) != func.sum(JournalLine.credit))
    ).all()
    assert unbalanced == []
    # the Inventory ledger always equals the yard stock value
    inventory = db.scalar(select(Account.id).where(Account.code == "1100"))
    stock_value = db.scalar(select(func.coalesce(func.sum(StockItem.value), 0)))
    assert balance_of(db, inventory) == Decimal(stock_value)
    # reversals mirror their original exactly
    for rev in db.scalars(select(JournalEntry).where(JournalEntry.reverses_id.is_not(None))):
        orig = db.get(JournalEntry, rev.reverses_id)
        pairs = sorted((ln.account_id, ln.debit, ln.credit) for ln in orig.lines)
        mirrored = sorted((ln.account_id, ln.credit, ln.debit) for ln in rev.lines)
        assert pairs == mirrored


def test_invariants_survive_edits_voids_and_counts(world, db):
    purchase(world, "20", "2000")
    purchase(world, "10", "2500")
    docs = [challan(world, str(q), freight_amount="100") for q in (1, 2, 3)]
    body = {"date": str(TODAY), "customer_id": world.customer["id"], "material_id": world.rait["id"], "qty": "5"}
    world.c.put(f"/api/v1/deliveries/{docs[0]['id']}", json=body, headers=world.h)
    world.post(f"/deliveries/{docs[1]['id']}/void", {"reason": "mistake entry"}, expect=200)
    p = world.get("/purchases")["items"][-1]
    world.post(f"/purchases/{p['id']}/void", {"reason": "bill returned"}, expect=200)
    world.post("/stock/counts", {"date": str(TODAY), "material_id": world.rait["id"], "physical_qty": "11.25"})
    assert_invariants(db)


def test_cannot_void_a_purchase_whose_stock_was_already_sold(world):
    p = purchase(world, "2", "2000")
    challan(world, "2")
    r = world.c.post(f"/api/v1/purchases/{p['id']}/void", json={"reason": "too late now"}, headers=world.h)
    assert r.status_code == 409 and r.json()["code"] == "INSUFFICIENT_STOCK"


def test_journal_line_check_constraint_rejects_two_sided_lines(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    acct = db.scalar(select(Account.id).limit(1))
    entry = JournalEntry(date=TODAY, source_type="x", narration="bad")
    entry.lines = [JournalLine(account_id=acct, debit=5, credit=5)]
    db.add(entry)
    with pytest.raises(IntegrityError):
        db.flush()


def test_posting_engine_refuses_unbalanced_entries(db):
    import pytest

    from app.accounting.posting import cr, dr, post
    from app.core.errors import UnbalancedJournal

    acct = db.scalar(select(Account.id).limit(1))
    with pytest.raises(UnbalancedJournal):
        post(db, date=TODAY, source_type="x", source_id=None, narration="x", lines=[dr(acct, 10), cr(acct, 9)])
    with pytest.raises(UnbalancedJournal):
        post(db, date=TODAY, source_type="x", source_id=None, narration="x", lines=[dr(acct, 10)])


def test_demo_seed_produces_balanced_books(db):
    """Runs the full 45-day demo scenario through every service."""
    from app.audit.hooks import install_audit_hooks
    from app.seed import run

    install_audit_hooks()
    run(db)
    assert_invariants(db)
    assert db.scalar(select(func.count()).select_from(JournalEntry)) > 500
