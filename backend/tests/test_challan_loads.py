"""Challans sold by half load, by dumper/loader bucket, and with a second material on the same trip."""

from decimal import Decimal

from tests.conftest import TODAY
from tests.test_core_flow import assert_books_balance, challan, purchase, stock_of


def cement(w, bags="100", rate="1300"):
    m = w.post(
        "/masters/materials",
        {"name": "Cement", "unit": "bag", "default_sale_rate": "1500", "default_purchase_rate": rate},
    )
    w.post("/purchases", {"date": TODAY.isoformat(), "supplier_id": w.supplier["id"],
                          "lines": [{"material_id": m["id"], "qty": bags, "rate": rate}]})  # fmt: skip
    return m


def set_loads(w, **fields):
    r = w.c.patch(f"/api/v1/masters/materials/{w.rait['id']}", json=fields, headers=w.h)
    assert r.status_code == 200, r.text


def test_half_trolley_takes_half_stock_at_full_rate(world):
    purchase(world, "10", "2000")
    d = challan(world, "1", load_size="half")
    assert Decimal(d["qty"]) == Decimal("0.5") and d["unit"] == "trolley" and d["load_size"] == "half"
    assert d["sale_rate"] == "3000.00" and Decimal(d["sale_amount"]) == 1500
    assert Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == Decimal("9.5")
    assert Decimal(d["cost_amount"]) == 1000
    assert_books_balance(world)


def test_half_not_allowed_for_bags(world):
    m = cement(world)
    r = world.c.post("/api/v1/deliveries", json={"date": TODAY.isoformat(),
                     "customer_id": world.customer["id"], "material_id": m["id"], "qty": "10", "load_size": "half"},
                     headers=world.h)  # fmt: skip
    assert r.status_code == 400 and r.json()["code"] == "HALF_NOT_ALLOWED"


def test_dumper_needs_a_size_then_converts_to_trolleys(world):
    purchase(world, "10", "2000")
    r = world.c.post("/api/v1/deliveries", json={"date": TODAY.isoformat(),
                     "customer_id": world.customer["id"], "material_id": world.rait["id"], "qty": "1",
                     "load_unit": "dumper"}, headers=world.h)  # fmt: skip
    assert r.status_code == 400 and r.json()["code"] == "LOAD_SIZE_MISSING"

    set_loads(world, dumper_qty="3")
    # no separate dumper rate: per-trolley rate x 3
    rate = world.get("/masters/rate", party_id=world.customer["id"], material_id=world.rait["id"], load_unit="dumper")
    assert rate["rate"] == "9000.00"
    d = challan(world, "1", load_unit="dumper", load_size="half")
    assert d["unit"] == "dumper" and Decimal(d["qty"]) == Decimal("0.5") and Decimal(d["stock_qty"]) == Decimal("1.5")
    assert Decimal(d["sale_amount"]) == 4500 and Decimal(d["cost_amount"]) == 3000
    assert Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == Decimal("8.5")
    assert_books_balance(world)


def test_bucket_uses_its_own_rate(world):
    purchase(world, "10", "2000")
    set_loads(world, bucket_qty="0.25", bucket_rate="900")
    d = challan(world, "4", load_unit="bucket")
    assert d["sale_rate"] == "900.00" and Decimal(d["sale_amount"]) == 3600 and Decimal(d["stock_qty"]) == 1
    assert_books_balance(world)


def test_rait_plus_cement_on_one_challan(world):
    purchase(world, "10", "2000")
    m = cement(world)
    d = challan(world, "1", extra_material_id=m["id"], extra_qty="20", freight_amount="500")
    assert d["extra_unit"] == "bag" and d["extra_rate"] == "1500.00" and Decimal(d["extra_amount"]) == 30000
    assert Decimal(d["extra_cost_amount"]) == 26000
    assert Decimal(stock_of(world, m["id"])["qty_on_hand"]) == 80
    # customer owes sand + cement + bhara
    assert world.balance(world.customer["account_id"]) == "33500.0"
    assert_books_balance(world)

    # editing away the cement puts the bags back; voiding restores everything
    body = {"date": d["date"], "customer_id": world.customer["id"], "material_id": world.rait["id"], "qty": "1"}
    r = world.c.put(f"/api/v1/deliveries/{d['id']}", json=body, headers=world.h)
    assert r.status_code == 200 and r.json()["extra_material_id"] is None and r.json()["extra_amount"] == "0.00"
    assert Decimal(stock_of(world, m["id"])["qty_on_hand"]) == 100
    world.post(f"/deliveries/{d['id']}/void", {"reason": "wrong trip"}, expect=200)
    assert Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == 10
    assert world.balance(world.customer["account_id"]) == "0.0"
    assert_books_balance(world)


def test_second_material_must_differ_and_have_qty(world):
    purchase(world)
    r = world.c.post("/api/v1/deliveries", json={"date": TODAY.isoformat(),
                     "customer_id": world.customer["id"], "material_id": world.rait["id"], "qty": "1",
                     "extra_material_id": world.rait["id"], "extra_qty": "1"}, headers=world.h)  # fmt: skip
    assert r.status_code == 400 and r.json()["code"] == "EXTRA_SAME_MATERIAL"


def test_half_trolley_shared_by_two_materials(world):
    purchase(world, "10", "2000")
    crush = world.post(
        "/masters/materials",
        {"name": "Crush", "unit": "trolley", "default_sale_rate": "4600", "default_purchase_rate": "3000"},
    )
    world.post("/purchases", {"date": str(TODAY), "supplier_id": world.supplier["id"],
                              "lines": [{"material_id": crush["id"], "qty": "4", "rate": "3000"}]})  # fmt: skip
    d = challan(world, "1", load_size="half", extra_material_id=crush["id"], extra_qty="0.5")
    assert Decimal(d["sale_amount"]) == 1500 and Decimal(d["extra_amount"]) == 2300
    assert Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == Decimal("9.5")
    assert Decimal(stock_of(world, crush["id"])["qty_on_hand"]) == Decimal("3.5")
    assert world.balance(world.customer["account_id"]) == "3800.0"
    assert_books_balance(world)
