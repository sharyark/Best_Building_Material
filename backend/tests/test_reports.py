import datetime as dt
from decimal import Decimal

from tests.conftest import TODAY
from tests.test_core_flow import challan, purchase


def build_month(w):
    """10 trolleys bought @2000, 3 sold, a payment, diesel, a loader rental, a daily worker."""
    purchase(w, "10", "2000")
    challan(w, "2", freight_amount="500")
    challan(w, "1", rate="3500")
    w.post(
        "/payments",
        {"date": str(TODAY), "direction": "in", "party_id": w.customer["id"], "money_account_id": w.cash["id"],
         "mode": "cash", "amount": "4000"},
    )  # fmt: skip
    w.post(
        "/expenses",
        {"date": str(TODAY), "category": "diesel", "vehicle_id": w.tractor["id"], "amount": "1500",
         "paid_via": "money_account", "money_account_id": w.cash["id"]},
    )  # fmt: skip
    w.post(
        "/rentals",
        {"date": str(TODAY), "customer_id": w.customer["id"], "vehicle_id": w.loader["id"], "basis": "hour",
         "qty": "4", "rate": "1200"},
    )  # fmt: skip
    w.c.put(
        "/api/v1/labour/attendance",
        json={"entries": [{"date": str(TODAY), "staff_id": w.labourer["id"], "status": "present"}]},
        headers=w.h,
    )


def test_khata_running_balance_and_totals(world):
    build_month(world)
    k = world.get(f"/reports/khata/{world.customer['id']}")
    rows = k["rows"]
    assert rows[0]["narration"] == "Opening balance" and rows[0]["balance"] == "0.00"
    # challans 6500 + 3500, receipt 4000, rental 4800
    assert [r["balance"] for r in rows[1:]] == ["6500.00", "10000.00", "6000.00", "10800.00"]
    assert k["totals"]["debit"] == "14800.00" and k["totals"]["credit"] == "4000.00"
    assert k["totals"]["balance"] == "10800.00"


def test_khata_opening_balance_respects_date_range(world):
    build_month(world)
    tomorrow = TODAY + dt.timedelta(days=1)
    k = world.get(f"/reports/khata/{world.customer['id']}", **{"from": str(tomorrow), "to": str(tomorrow)})
    assert k["rows"][0]["balance"] == "10800.00" and len(k["rows"]) == 1


def test_cash_book_and_day_book(world):
    build_month(world)
    cb = world.get("/reports/cash-book", money_account_id=world.cash["id"])
    assert cb["totals"]["money_in"] == "4000.00" and cb["totals"]["money_out"] == "1500.00"
    assert cb["totals"]["closing"] == "2500.00"
    db_ = world.get("/reports/day-book", date=str(TODAY))
    assert len(db_["rows"]) >= 7


def test_vehicle_pnl_uses_cost_centre(world):
    build_month(world)
    r = world.get("/reports/vehicle-pnl")
    by_name = {row["vehicle"]: row for row in r["rows"]}
    assert by_name["Tractor-1"]["revenue"] == "500.00"  # freight only
    assert by_name["Tractor-1"]["diesel"] == "1500.00" and by_name["Tractor-1"]["profit"] == "-1000.00"
    assert by_name["Tractor-1"]["trips"] == 2
    assert by_name["Loader-1"]["revenue"] == "4800.00" and by_name["Loader-1"]["profit"] == "4800.00"


def test_material_margin_and_pnl(world):
    build_month(world)
    m = world.get("/reports/material-margin")["rows"][0]
    assert m["qty"] == "3.000" and m["sale"] == "9500.00" and m["cost"] == "6000.00" and m["margin"] == "3500.00"
    pnl = world.get("/reports/profit-loss")
    # income 9500 sales + 500 freight + 4800 rent; expense COGS 6000 + diesel 1500 + wage 800
    assert pnl["meta"]["income"] == "14800.00" and pnl["meta"]["expense"] == "8300.00"
    assert pnl["meta"]["profit"] == "6500.00"


def test_outstanding_aging_buckets(world):
    purchase(world, "10", "2000")
    old = TODAY - dt.timedelta(days=70)
    mid = TODAY - dt.timedelta(days=40)
    for day, rate in ((old, "1000"), (mid, "2000"), (TODAY, "3000")):
        world.post(
            "/deliveries",
            {"date": str(day), "customer_id": world.customer["id"], "material_id": world.rait["id"], "qty": "1",
             "sale_rate": rate},
        )  # fmt: skip
    # payment of 1500 settles the oldest charge (1000) first, then 500 of the next
    world.post(
        "/payments",
        {"date": str(TODAY), "direction": "in", "party_id": world.customer["id"], "money_account_id": world.cash["id"],
         "mode": "cash", "amount": "1500"},
    )  # fmt: skip
    row = world.get("/reports/outstanding")["rows"][0]
    assert row["b60_plus"] == "0.00" and row["b31_60"] == "1500.00" and row["b0_30"] == "3000.00"
    assert row["total"] == "4500.00"


def test_yard_stock_report(world):
    build_month(world)
    r = world.get("/reports/yard-stock")["rows"][0]
    assert (r["opening"], r["qty_in"], r["qty_out"], r["closing"]) == ("0.000", "10.000", "3.000", "7.000")
    assert r["value"] == "14000.00" and r["avg_cost"] == "2000.00"


def test_labour_cost_and_staff_khata(world):
    build_month(world)
    lc = world.get("/reports/labour-cost", group_by="staff")
    assert lc["totals"]["amount"] == "800.00"
    sk = world.get(f"/reports/staff-khata/{world.labourer['id']}")
    assert sk["meta"]["days_present"] == 1 and sk["meta"]["wages_earned"] == "800.00"
    assert sk["meta"]["balance_payable"] == "800.00"


def test_rental_income_report(world):
    build_month(world)
    r = world.get("/reports/rental-income")["rows"][0]
    assert r["name"] == "Loader-1" and r["hours"] == "4.000" and r["income"] == "4800.00"
    by_customer = world.get("/reports/rental-income", group_by="customer")["rows"][0]
    assert by_customer["unpaid"] == "10800.00"


def test_dashboard(world):
    build_month(world)
    d = world.get("/reports/dashboard")
    assert d["trips_today"] == 2 and d["cash_in_hand"] == "2500.00"
    assert Decimal(d["total_receivable"]) == Decimal("10800.00") and Decimal(d["total_payable"]) == 20000
    assert d["stock_value"] == "14000.00"


def test_exports_xlsx_and_pdf(world):
    build_month(world)
    for path in (f"/reports/khata/{world.customer['id']}", "/reports/vehicle-pnl", "/reports/yard-stock"):
        x = world.c.get(f"/api/v1{path}", params={"format": "xlsx"}, headers=world.h)
        assert x.status_code == 200 and x.content[:2] == b"PK", path  # xlsx is a zip
        p = world.c.get(f"/api/v1{path}", params={"format": "pdf"}, headers=world.h)
        assert p.status_code == 200 and p.content[:4] == b"%PDF", path


def test_document_pdfs_and_whatsapp_share(world):
    build_month(world)
    ch = world.get("/deliveries")["items"][0]
    pay = world.get("/payments")["items"][0]
    for url in (f"/deliveries/{ch['id']}/pdf", f"/payments/{pay['id']}/pdf"):
        r = world.c.get(f"/api/v1{url}", headers=world.h)
        assert r.status_code == 200 and r.content[:4] == b"%PDF", url
    inv = world.post(
        "/invoices",
        {"date": str(TODAY), "customer_id": world.customer["id"], "period_from": str(TODAY), "period_to": str(TODAY),
         "delivery_ids": [ch["id"]]},
    )  # fmt: skip
    assert world.c.get(f"/api/v1/invoices/{inv['id']}/pdf", headers=world.h).content[:4] == b"%PDF"
    share = world.get(f"/reports/khata/{world.customer['id']}/share")
    assert share["url"].startswith("https://wa.me/0300111?text=") or share["url"].startswith("https://wa.me/300111")
    assert "10,800.00" in share["message"]
