"""Udhaar, on-the-spot payment and advance customers, all on the one customer khata."""

import datetime as dt
import uuid
from decimal import Decimal

from tests.conftest import TODAY
from tests.test_core_flow import assert_books_balance, challan, purchase


def receive(w, amount, day=TODAY):
    return w.post("/payments", {"date": str(day), "direction": "in", "party_id": w.customer["id"],
                                "money_account_id": w.cash["id"], "mode": "cash", "amount": amount})  # fmt: skip


def balance(w):
    return w.get(f"/masters/parties/{w.customer['id']}/balance")


def test_paid_on_the_spot_saves_a_receipt_and_leaves_khata_clear(world):
    purchase(world)
    d = challan(world, "1", freight_amount="500",
                payment={"amount": "3500", "money_account_id": world.cash["id"], "mode": "cash"})  # fmt: skip
    assert d["receipt_id"] is not None
    receipts = world.get("/payments", party_id=world.customer["id"])["items"]
    assert len(receipts) == 1 and receipts[0]["amount"] == "3500.00" and d["challan_no"] in receipts[0]["notes"]
    assert Decimal(balance(world)["balance"]) == 0
    assert_books_balance(world)


def test_part_paid_leaves_the_rest_as_udhaar(world):
    purchase(world)
    challan(world, "2", payment={"amount": "1000", "money_account_id": world.cash["id"]})
    b = balance(world)
    assert Decimal(b["balance"]) == 5000 and b["days_unpaid"] == 0


def test_resending_a_challan_does_not_take_the_payment_twice(world):
    purchase(world)
    ref = str(uuid.uuid4())
    body = {"payment": {"amount": "3000", "money_account_id": world.cash["id"]}, "client_ref": ref}
    first = challan(world, "1", **body)
    again = world.c.post(
        "/api/v1/deliveries",
        json={
            "date": str(TODAY),
            "customer_id": world.customer["id"],
            "material_id": world.rait["id"],
            "qty": "1",
            **body,
        },
        headers=world.h,
    )
    assert again.status_code == 200 and again.json()["id"] == first["id"]
    assert len(world.get("/payments", party_id=world.customer["id"])["items"]) == 1


def test_advance_is_used_up_by_challans(world):
    purchase(world)
    receive(world, "10000")
    b = balance(world)
    assert Decimal(b["balance"]) == -10000 and b["days_unpaid"] is None
    assert Decimal(b["advance_low_threshold"]) == 5000
    challan(world, "2")  # 6000 out of the 10000 advance
    assert Decimal(balance(world)["balance"]) == -4000
    challan(world, "2")  # advance gone, 2000 now on udhaar
    assert Decimal(balance(world)["balance"]) == 2000
    assert_books_balance(world)


def test_oldest_unpaid_is_first_in_first_out_and_ignores_voids(world):
    purchase(world, "20")
    old = TODAY - dt.timedelta(days=12)
    challan(world, "1", date=str(old))  # 3000, 12 days ago
    mid = challan(world, "1", date=str(TODAY - dt.timedelta(days=5)))  # 3000, 5 days ago
    assert balance(world)["days_unpaid"] == 12
    receive(world, "3000")  # pays off the oldest challan first
    assert balance(world)["days_unpaid"] == 5
    # a voided challan is not "paid" udhaar and doesn't make an older one look settled
    world.post(f"/deliveries/{mid['id']}/void", {"reason": "wrong trip"}, expect=200)
    b = balance(world)
    assert Decimal(b["balance"]) == 0 and b["days_unpaid"] is None


def test_dashboard_lists_low_advance_and_old_udhaar(world):
    purchase(world, "20")
    other = world.post("/masters/parties", {"type": "customer", "name": "Late Payer"})
    receive(world, "4000")  # Ali Builders: advance below the 5000 warning level
    world.post("/deliveries", {"date": str(TODAY - dt.timedelta(days=20)), "customer_id": other["id"],
                               "material_id": world.rait["id"], "qty": "1"})  # fmt: skip
    dash = world.get("/reports/dashboard")
    assert [r["name"] for r in dash["advance_low"]] == ["Ali Builders"] and dash["advance_low"][0][
        "advance"
    ] == "4000.00"
    assert dash["old_udhaar"] == [{"party_id": other["id"], "name": "Late Payer", "balance": "3000.00", "days": 20}]


def test_munshi_can_take_payment_with_a_challan(client, accountant, world):
    purchase(world)
    r = client.post(
        "/api/v1/deliveries",
        json={"date": str(TODAY), "customer_id": world.customer["id"], "material_id": world.rait["id"], "qty": "1",
              "payment": {"amount": "3000", "money_account_id": world.cash["id"]}},
        headers=accountant,
    )  # fmt: skip
    assert r.status_code == 201, r.text
    assert r.json()["receipt_id"]
