import os

os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["COOKIE_SECURE"] = "false"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret"

import datetime as dt  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.bootstrap import bootstrap  # noqa: E402
from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.auth.models import User  # noqa: E402

TODAY = dt.date.today()


@pytest.fixture(autouse=True)
def fresh_db():
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    else:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        bootstrap(db)
        db.add(User(name="Munshi", phone="munshi", password_hash=hash_password("munshi12345"), role="accountant"))
        db.commit()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _headers(db, phone: str) -> dict:
    user = db.query(User).filter_by(phone=phone).one()
    token, _ = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(db):
    return _headers(db, "admin")


@pytest.fixture
def accountant(db):
    return _headers(db, "munshi")


class World:
    """Small helper that creates master data through the real API."""

    def __init__(self, client: TestClient, headers: dict):
        self.c, self.h = client, headers

    def post(self, url: str, body: dict, expect: int = 201):
        r = self.c.post(f"/api/v1{url}", json=body, headers=self.h)
        assert r.status_code == expect, f"POST {url} -> {r.status_code}: {r.text}"
        return r.json() if r.content else None

    def get(self, url: str, expect: int = 200, **params):
        r = self.c.get(f"/api/v1{url}", params=params, headers=self.h)
        assert r.status_code == expect, f"GET {url} -> {r.status_code}: {r.text}"
        return r.json()

    def balance(self, account_id: int) -> str:
        tb = self.get("/accounting/trial-balance")
        for row in tb["rows"]:
            if row["account_id"] == account_id:
                return str(float(row["debit"]) - float(row["credit"]))
        return "0.0"


@pytest.fixture
def world(client, admin) -> World:
    w = World(client, admin)
    w.customer = w.post("/masters/parties", {"type": "customer", "name": "Ali Builders", "phone": "0300111"})
    w.supplier = w.post("/masters/parties", {"type": "supplier", "name": "Crusher X"})
    w.pump = w.post("/masters/parties", {"type": "supplier", "name": "Petrol Pump"})
    w.site = w.post("/masters/sites", {"party_id": w.customer["id"], "name": "Plot 12"})
    w.rait = w.post(
        "/masters/materials",
        {"name": "Rait", "unit": "trolley", "default_sale_rate": "3000", "default_purchase_rate": "2000"},
    )
    w.tractor = w.post("/masters/vehicles", {"type": "tractor_trolley", "name": "Tractor-1", "reg_no": "T-1"})
    w.loader = w.post("/masters/vehicles", {"type": "loader", "name": "Loader-1", "meter_type": "hours"})
    w.driver = w.post(
        "/masters/staff",
        {"name": "Ali Driver", "role": "driver", "wage_type": "monthly", "wage_amount": "18000",
         "default_vehicle_id": w.tractor["id"]},
    )  # fmt: skip
    w.labourer = w.post(
        "/masters/staff", {"name": "Raju", "role": "labour", "wage_type": "daily", "wage_amount": "800"}
    )
    w.cash = w.get("/masters/money-accounts")["items"][0]
    return w
