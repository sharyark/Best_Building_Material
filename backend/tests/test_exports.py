"""Day-wise backup exports (Excel/CSV) from the challan and purchase screens."""

import csv
import datetime as dt
import io

from tests.conftest import TODAY
from tests.test_core_flow import challan, purchase


def _csv(w, headers=None, **params) -> list[list[str]]:
    r = w.c.get("/api/v1/deliveries/export", params={"format": "csv", **params}, headers=headers or w.h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))


def test_export_defaults_to_today_and_includes_voided(world):
    purchase(world, "10", "2000")
    challan(world, "2", notes="gate 3")
    voided = challan(world, "1")
    world.post(f"/deliveries/{voided['id']}/void", {"reason": "wrong customer"}, expect=200)
    challan(world, "1", date=str(TODAY - dt.timedelta(days=3)))

    rows = _csv(world)
    header, body, total = rows[0], rows[1:-1], rows[-1]
    assert len(body) == 2  # only today's two, the older one is left out
    col = {name: i for i, name in enumerate(header)}
    assert body[0][col["Total"]] == "6000.00" and body[0][col["Notes"]] == "gate 3"
    assert body[1][col["Status"]] == "Void" and body[1][col["Void reason"]] == "wrong customer"
    assert total[0] == "Total (1 delivered)" and total[col["Total"]] == "6000.00"
    assert body[0][col["Edited"]] == ""
    assert "Cost" not in ",".join(header)  # no profit data for the munshi


def test_export_range_xlsx_and_filename(world, accountant):
    purchase(world, "10", "2000")
    challan(world, "1", date=str(TODAY - dt.timedelta(days=3)))
    challan(world, "1")
    start = TODAY - dt.timedelta(days=6)

    assert len(_csv(world, headers=accountant, **{"from": str(start), "to": str(TODAY)})) == 1 + 2 + 1

    r = world.c.get("/api/v1/deliveries/export", params={"from": str(start), "to": str(TODAY)}, headers=accountant)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert f"challans_{start}_to_{TODAY}.xlsx" in r.headers["content-disposition"]


def test_export_rejects_reversed_range(world):
    r = world.c.get(
        "/api/v1/deliveries/export",
        params={"from": str(TODAY), "to": str(TODAY - dt.timedelta(days=1))},
        headers=world.h,
    )
    assert r.status_code == 400 and r.json()["code"] == "BAD_DATE_RANGE"


def test_purchase_export_one_row_per_material(world, accountant):
    cement = world.post(
        "/masters/materials",
        {"name": "Cement", "unit": "bag", "default_sale_rate": "1500", "default_purchase_rate": "1300"},
    )
    world.post(
        "/purchases",
        {"date": str(TODAY), "supplier_id": world.supplier["id"], "supplier_slip_no": "S-9",
         "lines": [{"material_id": world.rait["id"], "qty": "10", "rate": "2000"},
                   {"material_id": cement["id"], "qty": "50", "rate": "1300"}]},
    )  # fmt: skip
    voided = purchase(world, "1", "2000")
    world.post(f"/purchases/{voided['id']}/void", {"reason": "duplicate"}, expect=200)
    purchase(world, "5", "2000", date=str(TODAY - dt.timedelta(days=2)))

    r = world.c.get("/api/v1/purchases/export", params={"format": "csv"}, headers=accountant)
    assert r.status_code == 200, r.text
    assert f"purchases_{TODAY}.csv" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    col = {name: i for i, name in enumerate(rows[0])}
    body, total = rows[1:-1], rows[-1]
    assert [b[col["Material"]] for b in body] == ["Rait", "Cement", "Rait"]
    assert body[1][col["Unit"]] == "bag" and body[1][col["Amount"]] == "65000.00"
    assert body[0][col["Bill total"]] == "85000.00" and body[0][col["Supplier slip"]] == "S-9"
    assert body[2][col["Status"]] == "Void" and body[2][col["Void reason"]] == "duplicate"
    assert total[0] == "Total (1 active)" and total[col["Amount"]] == "85000.00"

    x = world.c.get("/api/v1/purchases/export", headers=accountant)
    assert x.status_code == 200 and x.content[:2] == b"PK"
