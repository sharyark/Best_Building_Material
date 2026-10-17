import uuid
from decimal import Decimal

from tests.conftest import TODAY


def purchase(w, qty="10", rate="2000", **extra):
    return w.post(
        "/purchases",
        {"date": str(TODAY), "supplier_id": w.supplier["id"],
         "lines": [{"material_id": w.rait["id"], "qty": qty, "rate": rate}], **extra},
    )  # fmt: skip


def challan(w, qty="1", rate=None, **extra):
    body = {"date": str(TODAY), "customer_id": w.customer["id"], "site_id": w.site["id"],
            "material_id": w.rait["id"], "qty": qty, "vehicle_id": w.tractor["id"], **extra}  # fmt: skip
    if rate:
        body["sale_rate"] = rate
    return w.post("/deliveries", body)


def stock_of(w, material_id):
    return next(i for i in w.get("/stock") if i["material_id"] == material_id)


def assert_books_balance(w):
    tb = w.get("/accounting/trial-balance")
    assert tb["balanced"], tb
    assert Decimal(tb["total_debit"]) == Decimal(tb["total_credit"])


def test_purchase_updates_stock_and_supplier_khata(world):
    p = purchase(world)
    assert p["total"] == "20000.00" and p["bill_no"].startswith("PB/")
    s = stock_of(world, world.rait["id"])
    assert Decimal(s["qty_on_hand"]) == 10 and Decimal(s["avg_cost"]) == 2000 and Decimal(s["value"]) == 20000
    assert world.balance(world.supplier["account_id"]) == "-20000.0"  # we owe the crusher
    assert_books_balance(world)


def test_weighted_average_cost(world):
    purchase(world, "10", "2000")
    purchase(world, "10", "2400")
    s = stock_of(world, world.rait["id"])
    assert Decimal(s["avg_cost"]) == 2200 and Decimal(s["qty_on_hand"]) == 20


def test_challan_posts_sale_freight_and_cogs_at_average(world):
    purchase(world, "10", "2000")
    d = challan(world, "2", freight_amount="500")
    assert d["sale_rate"] == "3000.00"  # material default (no rate card)
    assert Decimal(d["sale_amount"]) == 6000 and Decimal(d["cost_amount"]) == 4000
    assert world.balance(world.customer["account_id"]) == "6500.0"
    s = stock_of(world, world.rait["id"])
    assert Decimal(s["qty_on_hand"]) == 8 and Decimal(s["value"]) == 16000
    assert_books_balance(world)


def test_rate_card_overrides_default(world):
    world.post(
        "/masters/rate-cards",
        {
            "party_id": world.customer["id"],
            "material_id": world.rait["id"],
            "rate": "2800",
            "effective_from": "2020-01-01",
        },
    )
    assert world.get("/masters/rate", party_id=world.customer["id"], material_id=world.rait["id"])["rate"] == "2800.00"
    purchase(world)
    assert challan(world)["sale_rate"] == "2800.00"


def test_negative_stock_blocked_unless_confirmed(world):
    purchase(world, "1")
    r = world.c.post(
        "/api/v1/deliveries",
        json={"date": str(TODAY), "customer_id": world.customer["id"], "material_id": world.rait["id"], "qty": "5"},
        headers=world.h,
    )
    assert r.status_code == 409 and r.json()["code"] == "INSUFFICIENT_STOCK"
    ok = challan(world, "5", allow_negative_stock=True)
    assert ok["status"] == "active"
    assert_books_balance(world)


def test_void_challan_restores_stock_and_reverses_journal(world):
    purchase(world)
    d = challan(world, "3")
    world.post(f"/deliveries/{d['id']}/void", {"reason": "wrong customer"}, expect=200)
    s = stock_of(world, world.rait["id"])
    assert Decimal(s["qty_on_hand"]) == 10 and Decimal(s["value"]) == 20000
    assert world.balance(world.customer["account_id"]) == "0.0"
    assert_books_balance(world)
    # voided document cannot be voided or edited again
    world.post(f"/deliveries/{d['id']}/void", {"reason": "again please"}, expect=409)


def test_edit_challan_reverses_and_reposts(world):
    purchase(world)
    d = challan(world, "1")
    body = {"date": str(TODAY), "customer_id": world.customer["id"], "material_id": world.rait["id"],
            "qty": "4", "sale_rate": "3100"}  # fmt: skip
    r = world.c.put(f"/api/v1/deliveries/{d['id']}", json=body, headers=world.h)
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["sale_amount"]) == 12400
    assert world.balance(world.customer["account_id"]) == "12400.0"
    assert Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == 6
    assert r.json()["challan_no"] == d["challan_no"]
    assert_books_balance(world)


def test_payment_in_and_out(world):
    purchase(world)
    challan(world, "1")
    world.post(
        "/payments",
        {"date": str(TODAY), "direction": "in", "party_id": world.customer["id"],
         "money_account_id": world.cash["id"], "mode": "cash", "amount": "1000"},
    )  # fmt: skip
    world.post(
        "/payments",
        {"date": str(TODAY), "direction": "out", "party_id": world.supplier["id"],
         "money_account_id": world.cash["id"], "mode": "cash", "amount": "5000"},
    )  # fmt: skip
    assert world.balance(world.customer["account_id"]) == "2000.0"
    assert world.balance(world.supplier["account_id"]) == "-15000.0"
    assert world.balance(world.cash["account_id"]) == "-4000.0"
    assert_books_balance(world)


def test_payment_needs_exactly_one_counterparty(world):
    r = world.c.post(
        "/api/v1/payments",
        json={
            "date": str(TODAY),
            "direction": "in",
            "money_account_id": world.cash["id"],
            "mode": "cash",
            "amount": "5",
        },
        headers=world.h,
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"


def test_client_ref_makes_create_idempotent(world):
    purchase(world)
    ref = str(uuid.uuid4())
    a = challan(world, "1", client_ref=ref)
    r = world.c.post(
        "/api/v1/deliveries",
        json={"date": str(TODAY), "customer_id": world.customer["id"], "material_id": world.rait["id"],
              "qty": "1", "client_ref": ref},
        headers=world.h,
    )  # fmt: skip
    assert r.status_code == 200 and r.json()["id"] == a["id"]
    assert Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == 9  # only one challan happened


def test_challan_numbers_are_sequential(world):
    purchase(world)
    nums = [challan(world)["challan_no"] for _ in range(3)]
    assert [n.rsplit("/", 1)[1] for n in nums] == ["00001", "00002", "00003"]


def test_month_lock_blocks_add_edit_and_void(world):
    purchase(world)
    d = challan(world)
    world.post("/accounting/locks", {"month": str(TODAY)})
    r = world.c.post("/api/v1/deliveries", json={"date": str(TODAY), "customer_id": world.customer["id"],
                                                 "material_id": world.rait["id"], "qty": "1"}, headers=world.h)  # fmt: skip
    assert r.status_code == 409 and r.json()["code"] == "PERIOD_LOCKED"
    world.post(f"/deliveries/{d['id']}/void", {"reason": "locked month"}, expect=409)
    world.c.delete(f"/api/v1/accounting/locks/{TODAY.replace(day=1)}", headers=world.h)
    world.post(f"/deliveries/{d['id']}/void", {"reason": "now unlocked"}, expect=200)


def test_diesel_on_pump_credit_charges_vehicle_cost_centre(world, db):
    from sqlalchemy import select

    from app.accounting.models import JournalLine

    world.post(
        "/expenses",
        {"date": str(TODAY), "category": "diesel", "vehicle_id": world.tractor["id"], "amount": "1500",
         "litres": "10", "paid_via": "party_credit", "party_id": world.pump["id"]},
    )  # fmt: skip
    assert world.balance(world.pump["account_id"]) == "-1500.0"
    lines = db.scalars(select(JournalLine).where(JournalLine.vehicle_id == world.tractor["id"])).all()
    assert len(lines) == 1 and lines[0].debit == 1500


def test_staff_advance_and_monthly_salary(world):
    world.post(
        "/payments",
        {"date": str(TODAY), "direction": "out", "staff_id": world.driver["id"], "purpose": "advance",
         "money_account_id": world.cash["id"], "mode": "cash", "amount": "2000"},
    )  # fmt: skip
    assert world.balance(world.driver["account_id"]) == "2000.0"
    start = TODAY.replace(day=1)
    s = world.post(
        "/labour/settlements", {"staff_id": world.driver["id"], "period_from": str(start), "period_to": str(TODAY)}
    )
    assert Decimal(s["gross"]) == 18000 and Decimal(s["advances_adjusted"]) == 2000
    assert Decimal(s["net_payable"]) == 16000
    assert world.balance(world.driver["account_id"]) == "-16000.0"  # owed to Ali after the advance
    assert_books_balance(world)


def test_daily_wage_accrues_per_attendance_and_updates(world):
    row = {"date": str(TODAY), "staff_id": world.labourer["id"], "status": "present"}
    world.c.put("/api/v1/labour/attendance", json={"entries": [row]}, headers=world.h)
    assert world.balance(world.labourer["account_id"]) == "-800.0"
    world.c.put(
        "/api/v1/labour/attendance",
        json={"entries": [{**row, "status": "half", "overtime_hours": "2"}]},
        headers=world.h,
    )
    assert world.balance(world.labourer["account_id"]) == "-600.0"  # 400 + 2h * 100
    world.c.put("/api/v1/labour/attendance", json={"entries": [{**row, "status": "absent"}]}, headers=world.h)
    assert world.balance(world.labourer["account_id"]) == "0.0"
    assert_books_balance(world)


def test_rental_income_and_invoice_with_tax(world):
    r = world.post(
        "/rentals",
        {"date": str(TODAY), "customer_id": world.customer["id"], "vehicle_id": world.loader["id"],
         "basis": "hour", "qty": "4", "rate": "1200"},
    )  # fmt: skip
    assert Decimal(r["amount"]) == 4800
    purchase(world)
    d = challan(world, "1")
    inv = world.post(
        "/invoices",
        {"date": str(TODAY), "customer_id": world.customer["id"], "period_from": str(TODAY), "period_to": str(TODAY),
         "delivery_ids": [d["id"]], "rental_ids": [r["id"]], "is_tax_invoice": True, "tax_rate": "10"},
    )  # fmt: skip
    assert Decimal(inv["subtotal"]) == 7800 and Decimal(inv["tax_amount"]) == 780 and Decimal(inv["total"]) == 8580
    assert world.balance(world.customer["account_id"]) == "8580.0"
    assert len(inv["lines"]) == 2
    # a challan on an invoice can't be voided until the invoice is
    world.post(f"/deliveries/{d['id']}/void", {"reason": "should fail"}, expect=409)
    world.post(f"/invoices/{inv['id']}/void", {"reason": "redo bill"}, expect=200)
    assert world.balance(world.customer["account_id"]) == "7800.0"
    world.post(f"/deliveries/{d['id']}/void", {"reason": "now allowed"}, expect=200)
    assert_books_balance(world)


def test_physical_count_posts_stock_loss(world):
    purchase(world, "10", "2000")
    c = world.post("/stock/counts", {"date": str(TODAY), "material_id": world.rait["id"], "physical_qty": "9.5"})
    assert Decimal(c["diff"]) == Decimal("-0.5")
    s = stock_of(world, world.rait["id"])
    assert Decimal(s["qty_on_hand"]) == Decimal("9.5") and Decimal(s["value"]) == 19000
    assert_books_balance(world)


def test_opening_balances_and_stock(world):
    world.post(
        "/accounting/opening-balances",
        [{"date": str(TODAY), "kind": "party", "ref_id": world.customer["id"], "side": "dr", "amount": "12000"},
         {"date": str(TODAY), "kind": "party", "ref_id": world.supplier["id"], "side": "cr", "amount": "7000"},
         {"date": str(TODAY), "kind": "money_account", "ref_id": world.cash["id"], "side": "dr", "amount": "5000"}],
        expect=204,
    )  # fmt: skip
    world.post(
        "/stock/opening",
        [{"date": str(TODAY), "material_id": world.rait["id"], "qty": "20", "rate": "1900"}],
        expect=204,
    )
    assert world.balance(world.customer["account_id"]) == "12000.0"
    assert world.balance(world.supplier["account_id"]) == "-7000.0"
    assert Decimal(stock_of(world, world.rait["id"])["value"]) == 38000
    listed = world.get("/stock/opening")
    assert len(listed) == 1 and Decimal(listed[0]["qty"]) == 20 and Decimal(listed[0]["rate"]) == 1900
    assert [o["name"] for o in world.get("/accounting/opening-balances")] == [
        "Cash in Hand",
        "Ali Builders",
        "Crusher X",
    ]
    # re-entering replaces rather than doubles
    world.post(
        "/accounting/opening-balances",
        [{"date": str(TODAY), "kind": "party", "ref_id": world.customer["id"], "side": "dr", "amount": "9000"}],
        expect=204,
    )  # fmt: skip
    assert world.balance(world.customer["account_id"]) == "9000.0"
    assert_books_balance(world)
