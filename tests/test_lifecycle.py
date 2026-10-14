"""Confirmation, rejection, cancellation, preparation and collection (BRD section 8)."""

import threading

import pytest

from campus_food import db, orders
from campus_food.errors import InvalidTransition, NotFound, ValidationError
from campus_food.status import Status


@pytest.fixture
def fruit_order(shop, aug4_1300):
    """A Submitted order for 2 Fruit Bowl at 4 Aug 13:00 (6 left before it, 4 after)."""
    return shop.order("Asha", aug4_1300, {"Fruit Bowl": 2})


# --- Happy path -----------------------------------------------------------------------------

def test_ac13_full_lifecycle_to_collected(shop, fruit_order):
    assert shop.staff(fruit_order, "confirm")["status"] == Status.CONFIRMED
    assert shop.staff(fruit_order, "start_preparing")["status"] == Status.PREPARING
    assert shop.staff(fruit_order, "mark_ready")["status"] == Status.READY
    assert shop.staff(fruit_order, "collect")["status"] == Status.COLLECTED


def test_ac10_confirm_and_preparation_do_not_touch_availability(shop, fruit_order, aug4_1300):
    assert shop.available(aug4_1300)["Fruit Bowl"] == 4
    for action in ("confirm", "start_preparing", "mark_ready"):
        shop.staff(fruit_order, action)
        assert shop.available(aug4_1300)["Fruit Bowl"] == 4


def test_ac17_collected_units_stay_consumed(shop, fruit_order, aug4_1300):
    shop.staff(fruit_order, "confirm", "start_preparing", "mark_ready", "collect")
    assert shop.available(aug4_1300)["Fruit Bowl"] == 4


# --- Rejection releases everything (BC-7) --------------------------------------------------

def test_ac09_rejection_closes_the_order_and_releases_all_lines(shop, aug4_1300):
    first = shop.order("A", aug4_1300, {"Fruit Bowl": 6, "Sprouts Salad": 3})  # both Healthy Food: one order
    assert shop.available(aug4_1300)["Fruit Bowl"] == 0
    rejected = shop.staff(first, "reject", reason="Kitchen closed early")
    assert rejected["status"] == Status.REJECTED
    assert rejected["reason"] == "Kitchen closed early"
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6
    assert shop.available(aug4_1300)["Sprouts Salad"] == 12
    second = shop.order("B", aug4_1300, {"Fruit Bowl": 6})  # a new pre-order from B now fits
    assert shop.status(second) == Status.SUBMITTED


def test_rejection_requires_a_reason(shop, fruit_order):
    with pytest.raises(ValidationError):
        shop.staff(fruit_order, "reject", reason="   ")
    assert shop.status(fruit_order) == Status.SUBMITTED


def test_rejection_releases_only_its_own_slot(shop, aug4_1230, aug4_1300):
    early = shop.order("A", aug4_1230, {"Fruit Bowl": 3})
    shop.order("B", aug4_1300, {"Fruit Bowl": 3})
    shop.staff(early, "reject", reason="test")
    assert shop.available(aug4_1230)["Fruit Bowl"] == 10
    assert shop.available(aug4_1300)["Fruit Bowl"] == 3


def test_confirmed_order_cannot_be_rejected(shop, fruit_order):
    shop.staff(fruit_order, "confirm")
    with pytest.raises(InvalidTransition):
        shop.staff(fruit_order, "reject", reason="too late")


# --- Cancellation (BC-8, BC-9) ---------------------------------------------------------------

def test_ac11_customer_cancels_confirmed_order_and_stock_is_released(shop, fruit_order, aug4_1300):
    shop.staff(fruit_order, "confirm")
    assert shop.cancel(fruit_order, "Asha")["status"] == Status.CANCELLED
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6


def test_customer_name_match_is_case_and_space_insensitive(shop, fruit_order):
    shop.staff(fruit_order, "confirm")
    assert shop.cancel(fruit_order, "  asha ")["status"] == Status.CANCELLED


@pytest.mark.parametrize("stages", [("confirm", "start_preparing"), ("confirm", "start_preparing", "mark_ready")])
def test_ac12_cancel_refused_once_preparation_has_started(shop, fruit_order, aug4_1300, stages):
    shop.staff(fruit_order, *stages)
    with pytest.raises(InvalidTransition, match="preparation has started"):
        shop.cancel(fruit_order, "Asha")
    assert shop.available(aug4_1300)["Fruit Bowl"] == 4


def test_submitted_order_cannot_be_cancelled_a07(shop, fruit_order):
    with pytest.raises(InvalidTransition, match="waiting for the outlet to accept"):
        shop.cancel(fruit_order, "Asha")


def test_another_customer_cannot_cancel(shop, fruit_order):
    shop.staff(fruit_order, "confirm")
    with pytest.raises(InvalidTransition, match="another customer"):
        shop.cancel(fruit_order, "Ben")
    assert shop.status(fruit_order) == Status.CONFIRMED


def test_staff_cannot_cancel_and_customers_cannot_run_staff_actions(shop, fruit_order):
    with pytest.raises(InvalidTransition):
        orders.transition(fruit_order, "cancel", orders.STAFF, db_path=shop.db_path)
    with pytest.raises(InvalidTransition):
        orders.transition(fruit_order, "confirm", orders.CUSTOMER, actor_name="Asha", db_path=shop.db_path)
    assert shop.status(fruit_order) == Status.SUBMITTED


# --- Collection (BC-11) ----------------------------------------------------------------------

def test_ac14_order_cannot_be_collected_twice(shop, fruit_order):
    shop.staff(fruit_order, "confirm", "start_preparing", "mark_ready", "collect")
    with pytest.raises(InvalidTransition, match="already been delivered"):
        shop.staff(fruit_order, "collect")


def test_two_staff_collecting_at_once_only_one_succeeds(shop, fruit_order):
    shop.staff(fruit_order, "confirm", "start_preparing", "mark_ready")
    barrier = threading.Barrier(2)
    outcomes = []

    def collect():
        barrier.wait()
        try:
            shop.staff(fruit_order, "collect")
            outcomes.append("collected")
        except InvalidTransition:
            outcomes.append("refused")

    threads = [threading.Thread(target=collect) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["collected", "refused"]


# --- Invalid transitions (LC-07) -------------------------------------------------------------

@pytest.mark.parametrize("action", ["confirm", "reject", "start_preparing", "mark_ready", "collect"])
def test_ac15_rejected_order_is_frozen(shop, fruit_order, action):
    shop.staff(fruit_order, "reject", reason="test")
    with pytest.raises(InvalidTransition, match="closed"):
        shop.staff(fruit_order, action, reason="again")
    assert shop.status(fruit_order) == Status.REJECTED


@pytest.mark.parametrize("action", ["confirm", "start_preparing", "mark_ready", "collect"])
def test_ac15_cancelled_order_is_frozen(shop, fruit_order, action):
    shop.staff(fruit_order, "confirm")
    shop.cancel(fruit_order, "Asha")
    with pytest.raises(InvalidTransition, match="closed"):
        shop.staff(fruit_order, action)
    assert shop.status(fruit_order) == Status.CANCELLED


@pytest.mark.parametrize("action", ["start_preparing", "mark_ready", "collect"])
def test_ac16_steps_cannot_be_skipped(shop, fruit_order, action):
    with pytest.raises(InvalidTransition):
        shop.staff(fruit_order, action)
    assert shop.status(fruit_order) == Status.SUBMITTED


def test_unknown_order_and_unknown_action(shop, fruit_order):
    with pytest.raises(NotFound):
        shop.staff(999, "confirm")
    with pytest.raises(ValidationError):
        shop.staff(fruit_order, "teleport")


def test_status_view_for_customer(shop, fruit_order, aug4_1230):
    other = shop.order("Ben", aug4_1230, {"Masala Dosa": 1})
    mine = orders.list_orders(customer_name="asha", db_path=shop.db_path)
    assert [order["id"] for order in mine] == [fruit_order]
    assert mine[0]["status"] == Status.SUBMITTED
    assert mine[0]["slot_label"] == "Tue 4 Aug 2026, 13:00-13:30"
    assert other not in [order["id"] for order in mine]


def test_staff_queue_filters_by_outlet_and_status(shop, fruit_order, aug4_1300, db_path):
    dosa = shop.order("Ben", aug4_1300, {"Masala Dosa": 1})
    with db.connection(db_path) as conn:
        healthy = conn.execute("SELECT id FROM outlet WHERE name = 'Healthy Food'").fetchone()["id"]
    healthy_queue = {order["id"] for order in orders.list_orders(outlet_id=healthy, statuses=[Status.SUBMITTED],
                                                                  db_path=db_path)}
    assert fruit_order in healthy_queue and dosa not in healthy_queue
    assert all(order["outlet"] == "Healthy Food"
               for order in orders.list_orders(outlet_id=healthy, db_path=db_path))
    submitted = {order["id"] for order in orders.list_orders(statuses=[Status.SUBMITTED], db_path=db_path)}
    assert {fruit_order, dosa} <= submitted
