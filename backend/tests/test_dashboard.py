"""Dashboard: today vs yesterday, money moved today, fleet, stock, and profit only for the owner."""

from decimal import Decimal

from tests.conftest import TODAY
from tests.test_core_flow import challan, purchase


def test_dashboard_today_money_fleet_stock(world, accountant):
    purchase(world, "10", "2000")
    challan(world, "2", payment={"amount": "1000", "money_account_id": world.cash["id"], "mode": "cash"})
    voided = challan(world, "1")
    world.post(f"/deliveries/{voided['id']}/void", {"reason": "mistake"}, expect=200)

    d = world.get("/reports/dashboard")
    assert d["trips_today"] == 2 and Decimal(d["sales_today"]) == 6000  # one challan of 2 trolleys = 2 trips
    assert len(d["daily"]) == 14 and d["daily"][-1] == {"date": str(TODAY), "sales": "6000.00", "trips": 2}
    # the voided challan's post + reversal is not "money moved"; the 1000 received is
    assert Decimal(d["money_in_today"]) == 1000

    tractor = next(v for v in d["vehicles"] if v["id"] == world.tractor["id"])
    assert tractor["trips"] == 2
    assert any(v["id"] == world.loader["id"] and v["trips"] == 0 for v in d["vehicles"])  # idle ones listed too

    assert {s["material"]: s["qty"] for s in d["stock"]}["Rait"] == "8.000"
    assert Decimal(d["profit_month"]["income"]) == 6000

    # the munshi sees everything except profit
    m = world.c.get("/api/v1/reports/dashboard", headers=accountant).json()
    assert m["profit_month"] is None and m["trips_today"] == 2


def test_dashboard_for_a_chosen_day_and_its_money_lines(world, accountant):
    import datetime as dt

    yesterday = TODAY - dt.timedelta(days=1)
    purchase(world, "10", "2000")
    challan(world, "3", date=str(yesterday), payment={"amount": "4000", "money_account_id": world.cash["id"], "mode": "cash"})  # fmt: skip
    world.post("/payments", {"date": str(yesterday), "direction": "out", "party_id": world.supplier["id"],
                             "money_account_id": world.cash["id"], "mode": "cash", "amount": "1500"})  # fmt: skip
    world.post("/expenses", {"date": str(yesterday), "category": "diesel", "vehicle_id": world.tractor["id"],
                             "litres": "10", "rate_per_litre": "280", "paid_via": "money_account",
                             "money_account_id": world.cash["id"]})  # fmt: skip
    challan(world, "1")  # today, on udhaar

    d = world.get("/reports/dashboard", on=str(yesterday))
    assert d["date"] == str(yesterday) and d["trips_today"] == 3 and Decimal(d["sales_today"]) == 9000
    assert Decimal(d["money_in_today"]) == 4000 and Decimal(d["money_out_today"]) == 4300  # 1500 + 2800 diesel
    assert world.get("/reports/dashboard")["trips_today"] == 1  # today is unchanged

    # clicking "Money paid out" lists each line, and the total matches the card
    out = world.c.get("/api/v1/reports/money-moves", params={"date": str(yesterday), "direction": "out"},
                      headers=accountant).json()  # fmt: skip
    assert out["totals"]["amount"] == "4300.00" and len(out["rows"]) == 2
    assert {r["type"] for r in out["rows"]} == {"Payment", "Expense"}
    inn = world.get("/reports/money-moves", date=str(yesterday), direction="in")
    assert inn["totals"]["amount"] == "4000.00" and inn["rows"][0]["account"] == world.cash["name"]
