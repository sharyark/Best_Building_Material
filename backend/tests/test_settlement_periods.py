"""A settlement covers its dates through period_to; the next one should start the day after, with no days lost."""

import datetime as dt

from tests.conftest import TODAY

D1 = TODAY - dt.timedelta(days=40)


def settle(w, start: dt.date, end: dt.date, expect=201, **extra):
    body = {"staff_id": w.labourer["id"], "period_from": str(start), "period_to": str(end), **extra}
    r = w.c.post("/api/v1/labour/settlements", json=body, headers=w.h)
    assert r.status_code == expect, r.text
    return r.json()


def preview(w, start: dt.date, end: dt.date):
    return w.get("/labour/settlements/preview", staff_id=w.labourer["id"], period_from=str(start), period_to=str(end))


def test_next_period_from_the_day_after_has_no_gap(world):
    first_end = D1 + dt.timedelta(days=9)
    settle(world, D1, first_end)
    p = preview(world, first_end + dt.timedelta(days=1), TODAY)
    assert p["last_settled_to"] == str(first_end) and p["gap_from"] is None and p["gap_to"] is None
    settle(world, first_end + dt.timedelta(days=1), TODAY)


def test_skipped_days_are_flagged_and_need_a_yes(world):
    first_end = D1 + dt.timedelta(days=9)
    settle(world, D1, first_end)
    later = first_end + dt.timedelta(days=6)
    p = preview(world, later, TODAY)
    assert p["gap_from"] == str(first_end + dt.timedelta(days=1)) and p["gap_to"] == str(later - dt.timedelta(days=1))

    err = settle(world, later, TODAY, expect=409)
    assert err["code"] == "PERIOD_GAP" and err["details"]["gap_from"] == p["gap_from"]
    assert first_end.strftime("%d-%m-%Y") in err["message"]

    settle(world, later, TODAY, allow_gap=True)  # e.g. the worker was away


def test_a_voided_settlement_does_not_count(world):
    first = settle(world, D1, D1 + dt.timedelta(days=9))
    world.post(f"/labour/settlements/{first['id']}/void", {"reason": "wrong dates"}, expect=200)
    p = preview(world, D1 + dt.timedelta(days=20), TODAY)
    assert p["last_settled_to"] is None and p["gap_from"] is None


def test_first_settlement_has_nothing_to_compare_with(world):
    p = preview(world, D1, TODAY)
    assert p["last_settled_to"] is None and p["gap_from"] is None
