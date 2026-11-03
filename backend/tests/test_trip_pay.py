"""Driver trip pay: each challan / own-vehicle purchase credits the driver's khata, trip payouts are kept apart
from salary, so after the weekly trip payout the khata is back to basic pay less advances."""

from decimal import Decimal

from tests.conftest import TODAY
from tests.test_core_flow import assert_books_balance, challan, purchase


def pay(w, amount, purpose, staff_id=None):
    return w.post(
        "/payments",
        {"date": str(TODAY), "direction": "out", "staff_id": staff_id or w.driver["id"], "purpose": purpose,
         "money_account_id": w.cash["id"], "mode": "cash", "amount": amount},
    )  # fmt: skip


def khata(w, staff_id=None):
    return w.get(f"/reports/staff-khata/{staff_id or w.driver['id']}")["meta"]


def D(v):
    return Decimal(str(v))


def test_trip_pay_builds_up_and_trip_payout_leaves_salary_untouched(world):
    driver = world.driver["id"]
    world.c.patch(f"/api/v1/masters/staff/{driver}", json={"wage_amount": "15000", "trip_rate": "200"}, headers=world.h)
    purchase(world, "10", "2000")

    first = challan(world, "1", driver_id=driver)  # no amount sent: the driver's usual rate
    assert first["trip_pay"] == "200.00"
    challan(world, "1", driver_id=driver, trip_pay="350")  # a long trip, typed by the munshi
    pay(world, "10000", "advance")

    k = khata(world)
    assert k["trips"] == 2 and D(k["trip_earned"]) == 550 and D(k["trip_balance"]) == 550
    # monthly, not settled yet: 15000 basic less the 10000 advance
    assert D(k["salary_left"]) == 5000 and D(k["salary_balance"]) == -10000

    pay(world, "550", "trip")  # the weekly trip payout
    k = khata(world)
    assert D(k["trip_paid"]) == 550 and D(k["trip_balance"]) == 0
    assert D(k["salary_left"]) == 5000

    # month end: salary posts, trip pay is not counted again
    settle = world.post(
        "/labour/settlements", {"staff_id": driver, "period_from": str(TODAY.replace(day=1)), "period_to": str(TODAY)}
    )
    assert settle["gross"] == "15000.00"
    k = khata(world)
    assert D(k["salary_left"]) == 5000 and D(k["balance_payable"]) == 5000
    assert_books_balance(world)


def test_void_and_edit_move_trip_pay(world):
    driver = world.driver["id"]
    purchase(world, "10", "2000")
    d = challan(world, "1", driver_id=driver, trip_pay="300")
    body = {"date": str(TODAY), "customer_id": world.customer["id"], "site_id": world.site["id"],
            "material_id": world.rait["id"], "qty": "1", "vehicle_id": world.tractor["id"], "driver_id": driver,
            "trip_pay": "250", "edit_reason": "trip pay agreed lower"}  # fmt: skip
    r = world.c.put(f"/api/v1/deliveries/{d['id']}", json=body, headers=world.h)
    assert r.status_code == 200 and r.json()["trip_pay"] == "250.00"
    assert D(khata(world)["trip_balance"]) == 250

    r = world.c.post(f"/api/v1/deliveries/{d['id']}/void", json={"reason": "wrong entry"}, headers=world.h)
    assert r.status_code == 200, r.text
    assert D(khata(world)["trip_balance"]) == 0
    assert_books_balance(world)


def test_trip_pay_on_own_vehicle_purchase_only(world):
    driver = world.driver["id"]
    p = purchase(world, "10", "2000", transport_by="own", vehicle_id=world.tractor["id"], driver_id=driver,
                 trip_pay="400")  # fmt: skip
    assert p["trip_pay"] == "400.00"
    # supplier delivered: no trip for our driver even if a figure is sent
    p = purchase(world, "5", "2000", trip_pay="400")
    assert p["trip_pay"] == "0.00"
    assert D(khata(world)["trip_balance"]) == 400


def test_trip_pay_needs_a_driver(world):
    purchase(world, "10", "2000")
    body = {"date": str(TODAY), "customer_id": world.customer["id"], "site_id": world.site["id"],
            "material_id": world.rait["id"], "qty": "1", "trip_pay": "200"}  # fmt: skip
    err = world.post("/deliveries", body, expect=400)
    assert err["code"] == "TRIP_PAY_NEEDS_DRIVER"


def test_per_trip_worker_is_not_paid_twice(world):
    temp = world.post(
        "/masters/staff", {"name": "Temp", "role": "driver", "wage_type": "per_trip", "wage_amount": "180"}
    )
    purchase(world, "10", "2000")
    challan(world, "1", vehicle_id=world.loader["id"], driver_id=temp["id"])  # rate defaults to his 180
    pv = world.get(
        "/labour/settlements/preview", staff_id=temp["id"], period_from=str(TODAY.replace(day=1)), period_to=str(TODAY)
    )
    assert pv["trips"] == 1 and pv["trip_pay"] == "180.00" and pv["gross"] == "0.00"
    assert D(khata(world, temp["id"])["trip_balance"]) == 180


def test_each_trolley_is_a_trip(world):
    driver = world.driver["id"]
    world.c.patch(f"/api/v1/masters/staff/{driver}", json={"trip_rate": "200"}, headers=world.h)
    purchase(world, "20", "2000")

    three = challan(world, "3", driver_id=driver)  # 3 trolleys of sand
    assert three["trips"] == 3 and three["trip_pay"] == "600.00"
    halves = challan(world, "2", driver_id=driver, load_size="half")  # two half trolleys: still two trips
    assert halves["trips"] == 2 and halves["trip_pay"] == "400.00"

    cement = world.post("/masters/materials", {"name": "Cement", "unit": "bag", "default_sale_rate": "1400"})
    world.post("/purchases", {"date": str(TODAY), "supplier_id": world.supplier["id"],
                              "lines": [{"material_id": cement["id"], "qty": "100", "rate": "1300"}]})  # fmt: skip
    bags = challan(world, "50", driver_id=driver, material_id=cement["id"])  # 50 bags on one trolley
    assert bags["trips"] == 1 and bags["trip_pay"] == "200.00"

    k = khata(world)
    assert k["trips"] == 6 and D(k["trip_earned"]) == 1200
    pv = world.get(
        "/labour/settlements/preview", staff_id=driver, period_from=str(TODAY.replace(day=1)), period_to=str(TODAY)
    )
    assert pv["trips"] == 6 and pv["trip_pay"] == "1200.00"


def test_vehicle_pnl_counts_loads_and_trip_pay(world):
    driver = world.driver["id"]
    world.c.patch(f"/api/v1/masters/staff/{driver}", json={"trip_rate": "200"}, headers=world.h)
    purchase(world, "10", "2000")
    challan(world, "3", driver_id=driver)
    row = next(r for r in world.get("/reports/vehicle-pnl")["rows"] if r["vehicle"] == "Tractor-1")
    assert row["trips"] == 3 and D(row["salary"]) == 600


def test_trips_on_every_vehicle_and_zero_means_none(world):
    driver = world.driver["id"]
    world.c.patch(f"/api/v1/masters/staff/{driver}", json={"trip_rate": "200"}, headers=world.h)
    op = world.post("/masters/staff", {"name": "Gulzar", "role": "operator", "wage_type": "monthly",
                                       "wage_amount": "26000", "trip_rate": "100",
                                       "default_vehicle_id": world.loader["id"]})  # fmt: skip
    world.c.patch(f"/api/v1/masters/materials/{world.rait['id']}", json={"bucket_qty": "0.25"}, headers=world.h)

    # own tractor brings 2 trolleys from the supplier = 2 trips
    p = purchase(world, "2", "2000", transport_by="own", vehicle_id=world.tractor["id"], driver_id=driver)
    assert p["trips"] == 2 and p["trip_pay"] == "400.00"
    purchase(world, "20", "2000")

    # loader sells 4 buckets = 4 trips for the operator
    b = challan(world, "4", vehicle_id=world.loader["id"], driver_id=op["id"], load_unit="bucket")
    assert b["trips"] == 4 and b["trip_pay"] == "400.00"

    # loader on rent: per trip -> qty trips; per hour -> one; the munshi can set 0 for no trip pay
    rent = {"date": str(TODAY), "customer_id": world.customer["id"], "vehicle_id": world.loader["id"],
            "operator_id": op["id"], "rate": "1200"}  # fmt: skip
    r = world.post("/rentals", {**rent, "basis": "trip", "qty": "3"})
    assert r["trips"] == 3 and r["trip_pay"] == "300.00"
    r = world.post("/rentals", {**rent, "basis": "hour", "qty": "5"})
    assert r["trips"] == 1 and r["trip_pay"] == "100.00"
    r = world.post("/rentals", {**rent, "basis": "hour", "qty": "2", "trip_pay": "0"})
    assert r["trip_pay"] == "0.00"

    k = khata(world, op["id"])
    assert k["trips"] == 8 and D(k["trip_earned"]) == 800  # 4 buckets + 3 + 1; the 0 one is not counted
    assert D(khata(world)["trip_earned"]) == 400
    assert_books_balance(world)


def test_pay_cut_needs_a_reason_that_shows_in_the_khata(world):
    import datetime as dt

    driver = world.driver["id"]  # monthly 18,000 -> 600 a day
    first = TODAY.replace(day=1)
    world.c.put("/api/v1/labour/attendance", headers=world.h, json={"entries": [
        {"date": str(first), "staff_id": driver, "status": "absent"},
        {"date": str(first + dt.timedelta(days=1)), "staff_id": driver, "status": "half"},
    ]})  # fmt: skip
    pv = world.get("/labour/settlements/preview", staff_id=driver, period_from=str(first), period_to=str(TODAY))
    assert pv["absent_days"] == "1.500" and pv["day_rate"] == "600.00"

    body = {"staff_id": driver, "period_from": str(first), "period_to": str(TODAY), "deductions": "900"}
    err = world.post("/labour/settlements", body, expect=400)
    assert err["code"] == "DEDUCTION_REASON_REQUIRED"
    s = world.post("/labour/settlements", {**body, "deduction_reason": "Chutti: 1.5 din"})
    assert s["deduction_reason"] == "Chutti: 1.5 din" and s["net_payable"] == "17100.00"
    rows = world.get(f"/reports/staff-khata/{driver}", **{"from": str(first), "to": str(TODAY)})["rows"]
    assert any("katoti 900.00: Chutti: 1.5 din" in r["narration"] for r in rows)


def test_settlement_uses_entered_advances_and_explains_an_overlap(world):
    driver = world.driver["id"]
    first = TODAY.replace(day=1)
    body = {"staff_id": driver, "period_from": str(first), "period_to": str(TODAY)}
    # an advance typed only into the settlement (not entered in Payments) is not counted
    s = world.post("/labour/settlements", {**body, "advances_adjusted": "5000"})
    assert s["advances_adjusted"] == "0.00" and s["net_payable"] == "18000.00"
    assert world.balance(world.driver["account_id"]) == "-18000.0"  # khata agrees with the settlement

    err = world.post("/labour/settlements", body, expect=409)
    assert err["code"] == "PERIOD_OVERLAP" and "Ali Driver is already settled for" in err["message"]
    assert "Payments" in err["message"]
