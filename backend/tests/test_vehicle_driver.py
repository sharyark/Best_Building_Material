"""Vehicle <-> driver: one driver per vehicle (set in Masters only); documents take that driver, and only
when he is absent or the vehicle has none may a free driver (not linked to any vehicle) be used."""

import datetime as dt

from tests.conftest import TODAY
from tests.test_core_flow import challan, purchase


def suggestion(w, vehicle_id, on=TODAY):
    return w.get(f"/masters/vehicles/{vehicle_id}/driver", on=str(on))


def mark(w, staff_id, status, on=TODAY):
    r = w.c.put(
        "/api/v1/labour/attendance",
        json={"entries": [{"date": str(on), "staff_id": staff_id, "status": status}]},
        headers=w.h,
    )
    assert r.status_code == 200, r.text


def new_driver(w, name, vehicle_id=None, expect=201):
    body = {
        "name": name,
        "role": "driver",
        "wage_type": "daily",
        "wage_amount": "900",
        "default_vehicle_id": vehicle_id,
    }
    return w.post("/masters/staff", body, expect=expect)


def test_vehicle_with_driver_is_locked_to_him(world):
    tractor, regular = world.tractor["id"], world.driver["id"]
    spare = new_driver(world, "Spare Driver")

    s = suggestion(world, tractor)
    assert s["driver_id"] == regular and s["source"] == "regular"
    assert s["locked"] and s["allowed_driver_ids"] == [regular]

    purchase(world, "10", "2000")
    err = world.post("/deliveries", {**_challan_body(world), "driver_id": spare["id"]}, expect=400)
    assert err["code"] == "DRIVER_NOT_ALLOWED"
    assert challan(world, "1", driver_id=regular)["driver_id"] == regular


def test_absent_driver_lets_a_free_driver_stand_in_for_the_day(world, accountant):
    tractor, regular = world.tractor["id"], world.driver["id"]
    spare = new_driver(world, "Spare Driver")
    other_vehicle = world.post("/masters/vehicles", {"type": "tractor_trolley", "name": "Tractor-2"})
    busy = new_driver(world, "Busy Driver", other_vehicle["id"])

    mark(world, regular, "absent")
    s = suggestion(world, tractor)
    assert s["driver_id"] is None and not s["locked"] and s["regular_absent"]
    # only drivers with no vehicle of their own; the other tractor's driver is not offered
    assert s["allowed_driver_ids"] == [spare["id"]]

    purchase(world, "10", "2000")
    err = world.post("/deliveries", {**_challan_body(world), "driver_id": busy["id"]}, expect=400)
    assert err["code"] == "DRIVER_NOT_ALLOWED"

    # the munshi picks the spare once; the vehicle's next entries that day get the spare
    challan(world, "1", driver_id=spare["id"])
    s = world.c.get(f"/api/v1/masters/vehicles/{tractor}/driver", params={"on": str(TODAY)}, headers=accountant).json()
    assert s["driver_id"] == spare["id"] and s["source"] == "today"

    # next day the regular driver is back and the vehicle is locked to him again
    tomorrow = TODAY + dt.timedelta(days=1)
    s = suggestion(world, tractor, tomorrow)
    assert s["driver_id"] == regular and s["locked"]


def test_vehicle_without_driver_offers_free_drivers_only(world):
    assert world.c.get("/api/v1/masters/vehicles/9999/driver", headers=world.h).status_code == 404

    # Loader-1 has no driver and every driver is linked: nobody to offer, so the form shows "add new"
    s = suggestion(world, world.loader["id"])
    assert s == {"driver_id": None, "source": None, "locked": False, "allowed_driver_ids": [],
                 "regular_driver_id": None, "regular_absent": False, "absent_driver_ids": []}  # fmt: skip

    temp = new_driver(world, "Temporary Driver")
    assert suggestion(world, world.loader["id"])["allowed_driver_ids"] == [temp["id"]]


def test_one_driver_per_vehicle_in_masters(world):
    tractor = world.tractor["id"]
    err = new_driver(world, "Second Driver", tractor, expect=409)
    assert err["code"] == "VEHICLE_HAS_DRIVER"

    spare = new_driver(world, "Spare Driver")
    r = world.c.patch(f"/api/v1/masters/staff/{spare['id']}", json={"default_vehicle_id": tractor}, headers=world.h)
    assert r.status_code == 409 and r.json()["code"] == "VEHICLE_HAS_DRIVER"

    # helpers and labour may share the vehicle as a cost centre
    helper = {"name": "Helper", "role": "helper", "wage_type": "per_trip", "wage_amount": "150"}
    world.post("/masters/staff", {**helper, "default_vehicle_id": tractor})

    # moving the regular driver off frees the vehicle for the spare
    r = world.c.patch(f"/api/v1/masters/staff/{world.driver['id']}", json={"default_vehicle_id": None}, headers=world.h)
    assert r.status_code == 200, r.text
    r = world.c.patch(f"/api/v1/masters/staff/{spare['id']}", json={"default_vehicle_id": tractor}, headers=world.h)
    assert r.status_code == 200, r.text
    assert suggestion(world, tractor)["driver_id"] == spare["id"]


def test_editing_an_old_entry_keeps_its_driver_after_masters_change(world):
    purchase(world, "10", "2000")
    d = challan(world, "1", driver_id=world.driver["id"])
    spare = new_driver(world, "Spare Driver")
    world.c.patch(f"/api/v1/masters/staff/{world.driver['id']}", json={"default_vehicle_id": None}, headers=world.h)
    world.c.patch(
        f"/api/v1/masters/staff/{spare['id']}", json={"default_vehicle_id": world.tractor["id"]}, headers=world.h
    )

    # same vehicle + driver as saved: the edit goes through even though the tractor now has another driver
    body = {**_challan_body(world), "qty": "2", "driver_id": world.driver["id"], "edit_reason": "qty fix"}
    r = world.c.put(f"/api/v1/deliveries/{d['id']}", json=body, headers=world.h)
    assert r.status_code == 200, r.text


def _challan_body(w):
    return {"date": str(TODAY), "customer_id": w.customer["id"], "site_id": w.site["id"],
            "material_id": w.rait["id"], "qty": "1", "vehicle_id": w.tractor["id"]}  # fmt: skip
