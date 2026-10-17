from decimal import Decimal

from tests.conftest import TODAY
from tests.test_core_flow import challan, purchase


def logs(world, **params):
    return world.get("/audit-logs", size=200, **params)["items"]


def test_create_update_void_are_audited_with_before_after(world):
    purchase(world)
    d = challan(world, "1")
    body = {"date": str(TODAY), "customer_id": world.customer["id"], "material_id": world.rait["id"],
            "qty": "2", "sale_rate": "3300"}  # fmt: skip
    world.c.put(f"/api/v1/deliveries/{d['id']}", json=body, headers=world.h)
    world.post(f"/deliveries/{d['id']}/void", {"reason": "customer cancelled"}, expect=200)
    entries = logs(world, entity="deliveries", entity_id=d["id"])
    assert [e["action"] for e in reversed(entries)][:1] == ["create"]
    assert {e["action"] for e in entries} == {"create", "update", "void"}
    update = next(e for e in entries if e["action"] == "update")
    assert Decimal(update["before"]["qty"]) == 1 and Decimal(update["after"]["qty"]) == 2
    void = next(e for e in entries if e["action"] == "void")
    assert void["after"]["void_reason"] == "customer cancelled"
    assert all(e["user_id"] for e in entries)


def test_audit_never_stores_password_hash(world):
    world.post("/users", {"name": "Imran", "phone": "0311", "password": "longenough1", "role": "driver"})
    rows = logs(world, entity="users")
    assert rows and all(r["after"]["password_hash"] == "***" for r in rows if r["action"] == "create")


def test_unlocking_a_month_is_audited(world):
    world.post("/accounting/locks", {"month": str(TODAY)})
    world.c.delete(f"/api/v1/accounting/locks/{TODAY.replace(day=1)}", headers=world.h)
    assert {e["action"] for e in logs(world, entity="period_locks")} == {"create", "delete"}
