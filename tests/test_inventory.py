"""Seed data, availability, all-or-nothing submission and two orders racing for the last units."""

import threading

import pytest

from campus_food import db, inventory, orders, seed_data
from campus_food.errors import AvailabilityError, NotFound, ValidationError
from campus_food.status import Status
from conftest import PDF_ITEMS


# --- Seed data exactly as the PDF and the outlet brief give it --------------------------

def test_menu_has_the_five_challenge_items_outlets_and_quantities(db_path):
    with db.connection(db_path) as conn:
        menu = {row["name"]: (row["category"], row["outlet"], row["qty_per_slot"]) for row in inventory.list_menu(conn)}
        outlets = [outlet["name"] for outlet in inventory.list_outlets(conn)]
    assert outlets == ["Coffee", "Fast Food", "Healthy Food", "Main Meal", "Pure Veg"]
    assert {name: value for name, value in menu.items() if name in PDF_ITEMS} == {
        "Cold Coffee": ("Beverages", "Coffee", 18),
        "Veg Sandwich": ("Snacks", "Fast Food", 20),
        "Paneer Rice Bowl": ("Meals", "Main Meal", 12),
        "Masala Dosa": ("South Indian", "Pure Veg", 15),
        "Fruit Bowl": ("Healthy Meals", "Healthy Food", 10),
    }


def test_ac01_availability_4_aug_1300(shop, aug4_1300):
    available = shop.availability(aug4_1300)
    assert shop.pdf_available(aug4_1300) == {
        "Veg Sandwich": 12, "Masala Dosa": 15, "Paneer Rice Bowl": 12, "Cold Coffee": 0, "Fruit Bowl": 6,
    }
    assert available["Cold Coffee"].state == inventory.RESTRICTED


def test_availability_4_aug_1230(shop, aug4_1230):
    available = shop.availability(aug4_1230)
    assert shop.pdf_available(aug4_1230) == {
        "Veg Sandwich": 20, "Masala Dosa": 15, "Paneer Rice Bowl": 7, "Cold Coffee": 0, "Fruit Bowl": 10,
    }
    assert available["Cold Coffee"].state == inventory.RESTRICTED


@pytest.mark.parametrize("slot_fixture", ["aug5_1230", "aug5_1300"])
def test_ac02_date_specific_conditions_do_not_carry_over_to_5_aug(shop, slot_fixture, request):
    slot_id = request.getfixturevalue(slot_fixture)
    assert shop.pdf_available(slot_id) == {
        "Veg Sandwich": 20, "Masala Dosa": 15, "Paneer Rice Bowl": 12, "Cold Coffee": 18, "Fruit Bowl": 10,
    }


def test_seed_commitments_are_confirmed_orders(db_path):
    seeded = orders.list_orders(customer_name=seed_data.SEED_CUSTOMER, db_path=db_path)
    assert len(seeded) == 3
    assert {order["status"] for order in seeded} == {Status.CONFIRMED}


# --- Submission: reserve all or nothing ---------------------------------------------------

def test_ac03_successful_submission_reserves_every_line(shop, aug4_1300):
    order_ids = shop.order("Asha", aug4_1300, {"Masala Dosa": 2, "Fruit Bowl": 1})
    assert [shop.status(order_id) for order_id in order_ids] == [Status.SUBMITTED, Status.SUBMITTED]
    available = shop.available(aug4_1300)
    assert available["Masala Dosa"] == 13
    assert available["Fruit Bowl"] == 5


def test_ac04_one_short_line_fails_the_whole_order_and_reserves_nothing(shop, aug4_1300):
    before = shop.order_count()
    with pytest.raises(AvailabilityError) as refused:
        shop.order("Asha", aug4_1300, {"Fruit Bowl": 6, "Veg Sandwich": 13})
    assert [f.item_name for f in refused.value.failures] == ["Veg Sandwich"]
    assert "Veg Sandwich: requested 13, only 12 left." in refused.value.message
    assert shop.order_count() == before
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6


def test_ac05_insufficient_quantity_is_refused(shop, aug4_1300):
    with pytest.raises(AvailabilityError) as refused:
        shop.order("Asha", aug4_1300, {"Fruit Bowl": 7})
    assert "Fruit Bowl: requested 7, only 6 left." in refused.value.message


def test_every_failing_line_is_reported(shop, aug4_1300):
    with pytest.raises(AvailabilityError) as refused:
        shop.order("Asha", aug4_1300, {"Fruit Bowl": 7, "Cold Coffee": 1, "Masala Dosa": 1})
    assert sorted(f.item_name for f in refused.value.failures) == ["Cold Coffee", "Fruit Bowl"]


def test_ac06_cold_coffee_refused_on_4_aug_but_accepted_on_5_aug(shop, aug4_1230, aug5_1230):
    with pytest.raises(AvailabilityError) as refused:
        shop.order("Asha", aug4_1230, {"Cold Coffee": 1})
    assert "Cold Coffee: temporarily unavailable (operational restriction)." in refused.value.message
    order_id = shop.order("Asha", aug5_1230, {"Cold Coffee": 1})
    assert shop.status(order_id) == Status.SUBMITTED
    assert shop.available(aug5_1230)["Cold Coffee"] == 17


def test_ac07_exact_remaining_quantity_then_sold_out(shop, aug4_1230):
    shop.order("Asha", aug4_1230, {"Paneer Rice Bowl": 7})
    item = shop.availability(aug4_1230)["Paneer Rice Bowl"]
    assert (item.available, item.state) == (0, inventory.SOLD_OUT)
    with pytest.raises(AvailabilityError) as refused:
        shop.order("Ben", aug4_1230, {"Paneer Rice Bowl": 1})
    assert "Paneer Rice Bowl: sold out for this slot" in refused.value.message


def test_each_slot_is_independent(shop, aug4_1230, aug4_1300):
    shop.order("Asha", aug4_1230, {"Fruit Bowl": 10})
    assert shop.available(aug4_1230)["Fruit Bowl"] == 0
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6


def test_repeated_items_are_merged_before_validation(shop, aug4_1300):
    fruit = shop.item("Fruit Bowl")
    with pytest.raises(AvailabilityError):
        orders.submit_order("Asha", aug4_1300, [(fruit, 3), (fruit, 4)], db_path=shop.db_path)
    order_id = orders.submit_order("Asha", aug4_1300, [(fruit, 2), (fruit, 2)], db_path=shop.db_path)
    (order_id,) = order_id.order_ids
    assert [(item["name"], item["qty"]) for item in orders.get_order(order_id, db_path=shop.db_path)["items"]] == [
        ("Fruit Bowl", 4)
    ]
    assert shop.available(aug4_1300)["Fruit Bowl"] == 2


# --- Input validation (AC-20, ERR-05, ERR-13) ----------------------------------------------

@pytest.mark.parametrize("qty", [0, -1, 1.5, "2", True])
def test_ac20_invalid_quantities_are_refused(shop, aug4_1300, qty):
    with pytest.raises(ValidationError):
        orders.submit_order("Asha", aug4_1300, {shop.item("Fruit Bowl"): qty}, db_path=shop.db_path)
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6


@pytest.mark.parametrize("name, cart", [("", {1: 1}), ("   ", {1: 1}), ("Asha", {}), ("Asha", {999: 1})])
def test_missing_name_empty_cart_or_unknown_item_is_refused(shop, aug4_1300, name, cart):
    with pytest.raises(ValidationError):
        orders.submit_order(name, aug4_1300, cart, db_path=shop.db_path)


def test_unknown_slot_is_refused(shop):
    with pytest.raises(NotFound):
        orders.submit_order("Asha", 999, {shop.item("Fruit Bowl"): 1}, db_path=shop.db_path)


# --- Concurrency: never overbook (AC-08, INV-08) --------------------------------------------

def _race(shop, slot_id, customers, quantities):
    """Start every submission at the same moment; return (successes, refusals)."""
    barrier = threading.Barrier(len(customers))
    successes, refusals, unexpected = [], [], []

    def submit(customer):
        barrier.wait()
        try:
            successes.append(shop.order(customer, slot_id, quantities))
        except AvailabilityError:
            refusals.append(customer)
        except Exception as exc:  # anything else is a defect
            unexpected.append(exc)

    threads = [threading.Thread(target=submit, args=(customer,)) for customer in customers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert unexpected == []
    return successes, refusals


def test_ac08_two_customers_racing_for_the_last_six_units(shop, aug4_1300):
    successes, refusals = _race(shop, aug4_1300, ["A", "B"], {"Fruit Bowl": 6})
    assert len(successes) == 1 and len(refusals) == 1
    assert shop.available(aug4_1300)["Fruit Bowl"] == 0


def test_twelve_simultaneous_orders_never_exceed_capacity(shop, aug4_1300):
    successes, refusals = _race(shop, aug4_1300, [f"C{i}" for i in range(12)], {"Fruit Bowl": 1})
    assert len(successes) == 6 and len(refusals) == 6
    item = shop.availability(aug4_1300)["Fruit Bowl"]
    assert item.used == item.capacity == 10
