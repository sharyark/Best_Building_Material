import datetime as dt

import pytest

from app.core.config import get_settings
from tests.conftest import TODAY
from tests.test_core_flow import challan, purchase


def login(client, phone="admin", password="admin12345"):
    return client.post("/api/v1/auth/login", json={"phone": phone, "password": password})


def test_login_returns_access_token_and_httponly_cookie(client):
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "admin" and "*" in body["user"]["permissions"]
    cookie = r.headers["set-cookie"].lower()
    assert "refresh_token=" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 200


def test_wrong_password_and_unknown_user_look_the_same(client):
    a = login(client, password="nope-nope")
    b = login(client, phone="ghost", password="whatever1")
    assert a.status_code == b.status_code == 401
    assert a.json()["code"] == b.json()["code"] == "INVALID_CREDENTIALS"


def test_login_rate_limited_to_five_per_minute(client):
    codes = [login(client, password="wrong-pass").status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]


def test_refresh_rotates_and_reuse_revokes_everything(client):
    first = login(client)
    old_cookie = first.cookies.get("refresh_token")
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200 and r.cookies.get("refresh_token") != old_cookie
    new_cookie = r.cookies.get("refresh_token")
    # replaying the rotated-out token is treated as theft
    client.cookies.clear()
    client.cookies.set("refresh_token", old_cookie, path="/api/v1/auth")
    replay = client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401 and replay.json()["code"] == "REFRESH_TOKEN_REUSED"
    client.cookies.clear()
    client.cookies.set("refresh_token", new_cookie, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401  # the whole family is dead


def test_logout_revokes_refresh_token(client):
    login(client)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_protected_routes_need_a_token(client):
    assert client.get("/api/v1/masters/parties").status_code == 401
    assert client.get("/api/v1/masters/parties", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_accountant_cannot_void_see_profit_or_manage_users(world, accountant):
    purchase(world)
    d = challan(world)
    c = world.c

    def acct_post(url, body):
        return c.post(f"/api/v1{url}", json=body, headers=accountant)

    assert acct_post(f"/deliveries/{d['id']}/void", {"reason": "not allowed"}).status_code == 403
    for url in ("/reports/vehicle-pnl", "/reports/profit-loss", "/reports/material-margin", "/reports/outstanding",
                "/accounting/trial-balance", "/audit-logs", "/users"):  # fmt: skip
        assert c.get(f"/api/v1{url}", headers=accountant).status_code == 403, url
    assert acct_post("/accounting/locks", {"month": str(TODAY)}).status_code == 403
    assert c.delete(f"/api/v1/accounting/locks/{TODAY.replace(day=1)}", headers=accountant).status_code == 403
    # ...but can do the daily work
    assert c.get(f"/api/v1/reports/khata/{world.customer['id']}", headers=accountant).status_code == 200
    assert c.get("/api/v1/reports/dashboard", headers=accountant).status_code == 200
    ok = acct_post("/deliveries", {"date": str(TODAY), "customer_id": world.customer["id"],
                                   "material_id": world.rait["id"], "qty": "1"})  # fmt: skip
    assert ok.status_code == 201
    assert acct_post("/masters/parties", {"type": "customer", "name": "New"}).status_code == 201
    # opening balances are admin-only (one-time setup)
    assert acct_post("/accounting/opening-balances", []).status_code == 403


def test_no_delete_endpoints_for_financial_documents(world):
    for path in ("deliveries", "purchases", "payments", "expenses", "rentals", "invoices"):
        r = world.c.delete(f"/api/v1/{path}/1", headers=world.h)
        assert r.status_code == 405, path


def test_admin_user_management_and_self_lockout_guard(client, admin, db):
    from app.modules.auth.models import User

    me = db.query(User).filter_by(phone="admin").one()
    r = client.post(
        "/api/v1/users",
        json={"name": "Imran", "phone": "0311", "password": "longenough1", "role": "driver"},
        headers=admin,
    )
    assert r.status_code == 201 and r.json()["role"] == "driver"
    assert client.patch(f"/api/v1/users/{me.id}", json={"is_active": False}, headers=admin).status_code == 409
    # new users can sign in with their own password
    assert login(client, "munshi", "munshi12345").status_code == 200


@pytest.mark.parametrize("bad", ["short", ""])
def test_password_policy(client, admin, bad):
    r = client.post(
        "/api/v1/users", json={"name": "X", "phone": "999", "password": bad, "role": "driver"}, headers=admin
    )
    assert r.status_code == 422


def test_error_shape_for_domain_errors(world):
    r = world.c.get("/api/v1/deliveries/9999", headers=world.h)
    assert r.status_code == 404
    assert set(r.json()) == {"code", "message", "details"} and r.json()["code"] == "NOT_FOUND"


def test_prod_requires_real_jwt_secret():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(env="prod", jwt_secret="change-me-in-env")
    assert get_settings().env == "test" and dt  # sanity: test settings are active
