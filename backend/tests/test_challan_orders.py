"""A challan starts as an order and reaches the khata, trip pay and stock only once it is marked delivered."""

from decimal import Decimal

from tests.conftest import TODAY
from tests.test_core_flow import assert_books_balance, challan, purchase, stock_of


def order(w, **extra):
    return challan(w, "2", driver_id=w.driver["id"], trip_pay="500", delivered=False, **extra)


def khata(w) -> Decimal:
    return Decimal(w.get(f"/masters/parties/{w.customer['id']}/balance")["balance"])


def driver_owed(w) -> Decimal:
    return -Decimal(w.balance(w.driver["account_id"]))


def test_order_posts_nothing_until_delivered(world):
    purchase(world)
    d = order(world)
    assert d["delivered"] is False and d["journal_id"] is None and d["challan_no"]
    assert khata(world) == 0 and driver_owed(world) == 0
    assert Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == 10
    assert world.get("/reports/dashboard")["pending_orders"] == 1
    assert Decimal(world.get("/reports/dashboard")["sales_today"]) == 0

    d = world.post(f"/deliveries/{d['id']}/deliver", {}, expect=200)
    assert d["delivered"] is True and d["delivered_at"] and d["journal_id"]
    assert khata(world) == 6000 and driver_owed(world) == 500
    assert Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == 8
    assert Decimal(d["cost_amount"]) == 4000  # cost taken when it left the yard
    assert world.get("/reports/dashboard")["pending_orders"] == 0
    assert_books_balance(world)

    r = world.c.post(f"/api/v1/deliveries/{d['id']}/deliver", json={}, headers=world.h)
    assert r.status_code == 409 and r.json()["code"] == "ALREADY_DELIVERED"


def test_munshi_cannot_change_a_delivered_challan_but_the_owner_can(world, accountant):
    purchase(world)
    d = order(world)
    body = {"date": str(TODAY), "customer_id": world.customer["id"], "material_id": world.rait["id"], "qty": "3",
            "vehicle_id": world.tractor["id"], "delivered": False, "edit_reason": "3 trolleys"}  # fmt: skip

    r = world.c.put(f"/api/v1/deliveries/{d['id']}", json=body, headers=accountant)
    assert r.status_code == 200 and Decimal(r.json()["qty"]) == 3 and khata(world) == 0  # still an order

    r = world.c.post(f"/api/v1/deliveries/{d['id']}/deliver", json={}, headers=accountant)
    assert r.status_code == 200 and khata(world) == 9000

    r = world.c.put(f"/api/v1/deliveries/{d['id']}", json={**body, "delivered": True}, headers=accountant)
    assert r.status_code == 403 and r.json()["code"] == "CHALLAN_DELIVERED"

    r = world.c.put(f"/api/v1/deliveries/{d['id']}", json=body, headers=world.h)
    assert r.status_code == 409 and r.json()["code"] == "DELIVERED_IS_FINAL"

    r = world.c.put(
        f"/api/v1/deliveries/{d['id']}", json={**body, "qty": "1", "delivered": True, "edit_reason": "only 1"},
        headers=world.h,
    )  # fmt: skip
    assert r.status_code == 200 and r.json()["delivered"] is True and khata(world) == 3000
    assert Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == 9
    assert_books_balance(world)


def test_ticking_delivered_on_the_form_posts_at_once(world):
    purchase(world)
    d = challan(world, "1", delivered=True)
    assert d["delivered"] is True and khata(world) == 3000


def test_voiding_an_order_reverses_nothing(world):
    purchase(world)
    d = order(world)
    world.post(f"/deliveries/{d['id']}/void", {"reason": "order cancelled"}, expect=200)
    assert khata(world) == 0 and Decimal(stock_of(world, world.rait["id"])["qty_on_hand"]) == 10
    r = world.c.post(f"/api/v1/deliveries/{d['id']}/deliver", json={}, headers=world.h)
    assert r.status_code == 409 and r.json()["code"] == "DOCUMENT_VOID"
    assert_books_balance(world)


def test_money_paid_with_an_order_is_received_at_once(world):
    purchase(world)
    order(world, payment={"amount": "2000", "money_account_id": world.cash["id"]})
    assert khata(world) == -2000  # an advance until the order is delivered


def test_orders_cannot_be_billed(world):
    purchase(world)
    d = order(world)
    assert world.get("/invoices/uninvoiced", customer_id=world.customer["id"])["deliveries"] == []
    r = world.c.post(
        "/api/v1/invoices",
        json={"date": str(TODAY), "customer_id": world.customer["id"], "period_from": str(TODAY),
              "period_to": str(TODAY), "delivery_ids": [d["id"]]},
        headers=world.h,
    )  # fmt: skip
    assert r.status_code == 409 and r.json()["code"] == "NOT_DELIVERED"
