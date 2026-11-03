"""Fuel: the munshi enters litres and the pump's rate; the amount, the pump's khata and the fuel report follow."""

from decimal import Decimal

from tests.conftest import TODAY


def fuel(w, litres, rate, **extra):
    body = {"date": str(TODAY), "category": "diesel", "vehicle_id": w.tractor["id"], "litres": litres,
            "rate_per_litre": rate, "paid_via": "party_credit", "party_id": w.pump["id"], **extra}  # fmt: skip
    return w.post("/expenses", body)


def test_amount_is_litres_times_rate_on_the_pump_khata(world):
    e = fuel(world, "40", "280.50")
    assert e["amount"] == "11220.00" and e["rate_per_litre"] == "280.50"
    fuel(world, "25.5", "281")  # 7165.50
    # the pump is owed both fills; paying it weekly brings it down
    assert world.balance(world.pump["account_id"]) == "-18385.5"
    world.post(
        "/payments",
        {"date": str(TODAY), "direction": "out", "party_id": world.pump["id"], "money_account_id": world.cash["id"],
         "mode": "cash", "amount": "10000"},
    )  # fmt: skip
    assert world.balance(world.pump["account_id"]) == "-8385.5"

    khata = world.get(f"/reports/khata/{world.pump['id']}")
    assert any("diesel 40 L @ 280.50 = 11,220.00" in r["narration"] for r in khata["rows"])


def test_last_rate_prefills_and_rate_needs_litres(world):
    assert world.get("/expenses/fuel-rate")["rate_per_litre"] is None
    fuel(world, "10", "279")
    assert world.get("/expenses/fuel-rate", party_id=world.pump["id"])["rate_per_litre"] == "279.00"

    bad = {"date": str(TODAY), "category": "diesel", "rate_per_litre": "280", "paid_via": "money_account",
           "money_account_id": world.cash["id"]}  # fmt: skip
    assert world.c.post("/api/v1/expenses", json=bad, headers=world.h).status_code == 422
    # other expenses still take a plain amount
    world.post("/expenses", {"date": str(TODAY), "category": "repair", "amount": "1500", "paid_via": "money_account",
                             "money_account_id": world.cash["id"]})  # fmt: skip


def test_fuel_report_by_vehicle_and_pump(world):
    fuel(world, "40", "280")  # 11200 on credit
    fuel(world, "10", "290", paid_via="money_account", money_account_id=world.cash["id"], party_id=None)  # 2900 cash
    row = world.get("/reports/fuel")["rows"][0]
    assert row["name"] == "Tractor-1" and row["fills"] == 2 and row["litres"] == "50.000"
    assert row["amount"] == "14100.00" and row["on_credit"] == "11200.00" and row["avg_rate"] == "282.00"
    pumps = {r["name"]: r for r in world.get("/reports/fuel", group_by="pump")["rows"]}
    assert pumps["Petrol Pump"]["amount"] == "11200.00" and pumps["Paid in cash"]["amount"] == "2900.00"
    assert Decimal(world.get("/reports/fuel")["totals"]["litres"]) == 50


def test_nightly_food_money_is_its_own_expense(world):
    e = world.post("/expenses", {"date": str(TODAY), "category": "food", "amount": "1200", "paid_via": "money_account",
                                 "money_account_id": world.cash["id"], "notes": "raat ka khana"})  # fmt: skip
    assert e["category"] == "food"
    assert world.balance(world.cash["account_id"]) == "-1200.0"
    pnl = {r["name"]: r["amount"] for r in world.get("/reports/profit-loss")["rows"]}
    assert pnl["Expense - Food (khana)"] == "1200.00"
    out = world.get("/reports/money-moves", date=str(TODAY), direction="out")
    assert out["totals"]["amount"] == "1200.00" and "food" in out["rows"][0]["narration"]
    # food has no litres
    bad = {"date": str(TODAY), "category": "food", "amount": "500", "litres": "2", "paid_via": "money_account",
           "money_account_id": world.cash["id"]}  # fmt: skip
    assert world.c.post("/api/v1/expenses", json=bad, headers=world.h).status_code == 422
