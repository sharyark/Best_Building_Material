"""Cement types: one group, each type with its own price and stock; names and prices change from Masters."""

from tests.conftest import TODAY
from tests.test_core_flow import challan


def test_each_type_sells_at_its_own_price_and_stock(world):
    types = {
        name: world.post("/masters/materials", {"name": name, "unit": "bag", "group_name": " cement ",
                                                "default_sale_rate": rate, "default_purchase_rate": "1300"})
        for name, rate in (("Cement - OPC", "1520"), ("Cement - SRC", "1650"), ("Cement - White", "2800"))
    }  # fmt: skip
    assert {t["group_name"] for t in types.values()} == {"Cement"}  # trimmed and capitalised: one group
    world.post("/purchases", {"date": str(TODAY), "supplier_id": world.supplier["id"], "lines": [
        {"material_id": t["id"], "qty": "50", "rate": "1300"} for t in types.values()]})  # fmt: skip

    src = types["Cement - SRC"]
    rate = world.get("/masters/rate", party_id=world.customer["id"], material_id=src["id"], date=str(TODAY))
    assert rate["rate"] == "1650.00"
    d = challan(world, "10", material_id=src["id"], sale_rate=rate["rate"])
    assert d["sale_amount"] == "16500.00"
    stock = {s["material_id"]: s["qty_on_hand"] for s in world.get("/stock")}
    assert stock[src["id"]] == "40.000" and stock[types["Cement - OPC"]["id"]] == "50.000"

    # the owner renames a type and changes its price in Masters; the next challan uses it
    r = world.c.patch(f"/api/v1/masters/materials/{src['id']}",
                      json={"name": "Cement - SRC (Lucky)", "default_sale_rate": "1700"}, headers=world.h)  # fmt: skip
    assert r.status_code == 200 and r.json()["group_name"] == "Cement"
    assert world.get("/masters/rate", party_id=world.customer["id"], material_id=src["id"])["rate"] == "1700.00"

    # blank group = not grouped
    r = world.c.patch(f"/api/v1/masters/materials/{src['id']}", json={"group_name": "  "}, headers=world.h)
    assert r.json()["group_name"] is None
