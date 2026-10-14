"""Pricing, one order per outlet, demo payment, preparation time, reorder and vendor metrics."""

from datetime import date

import pytest

from campus_food import db, orders, pricing
from campus_food.errors import AvailabilityError, InvalidTransition, NotFound, ValidationError
from campus_food.status import Status


def _quote(shop, cart):
    with db.connection(shop.db_path) as conn:
        return pricing.quote(conn, cart)


# --- Pricing ---------------------------------------------------------------------------------

def test_quote_groups_by_outlet_and_adds_tax_and_fee(shop):
    cart = [
        {"item_id": shop.item("Veg Sandwich"), "qty": 2, "options": ["Extra cheese"]},  # (60 + 15) x 2 = 150
        {"item_id": shop.item("Fruit Bowl"), "qty": 1, "options": []},                  # 90
    ]
    quote = _quote(shop, cart)
    assert [o.outlet_name for o in quote.outlets] == ["Fast Food", "Healthy Food"]
    fast, healthy = quote.outlets
    assert (fast.subtotal, fast.tax, fast.fee, fast.total) == (15000, 750, 500, 16250)
    assert (healthy.subtotal, healthy.tax, healthy.fee, healthy.total) == (9000, 450, 500, 9950)
    assert quote.total == 16250 + 9950
    assert fast.lines[0].unit_price == 7500 and fast.lines[0].options == ("Extra cheese",)
    assert fast.prep_minutes == 8


def test_tax_rounds_half_up_to_the_paisa():
    assert pricing.tax_on(2510) == 126  # 5% of ₹25.10 = 125.5 paise
    assert pricing.tax_on(2500) == 125


def test_same_item_with_different_options_stays_on_separate_lines(shop):
    sandwich = shop.item("Veg Sandwich")
    quote = _quote(shop, [
        {"item_id": sandwich, "qty": 1, "options": ["Extra cheese"]},
        {"item_id": sandwich, "qty": 1, "options": []},
        {"item_id": sandwich, "qty": 2, "options": ["Extra cheese"]},
    ])
    assert sorted((line.qty, line.options) for line in quote.outlets[0].lines) == [(1, ()), (3, ("Extra cheese",))]


def test_unknown_option_is_refused(shop):
    with pytest.raises(ValidationError, match="not an option"):
        _quote(shop, [{"item_id": shop.item("Fruit Bowl"), "qty": 1, "options": ["Extra cheese"]}])


def test_rupee_formatting():
    assert pricing.rupees(16250) == "₹162.50"
    assert pricing.rupees(150000) == "₹1,500"


# --- Checkout: one order per outlet, all or nothing ------------------------------------------

def test_cart_across_outlets_creates_one_priced_order_per_outlet(shop, aug4_1300):
    checkout = shop.checkout("Asha", aug4_1300, {"Masala Dosa": 2, "Fruit Bowl": 1})
    placed = orders.list_orders(checkout_id=checkout.checkout_id, db_path=shop.db_path)
    assert sorted(o["outlet"] for o in placed) == ["Healthy Food", "Pure Veg"]
    for order in placed:
        assert order["status"] == Status.PLACED
        assert order["payment_status"] == "Pending" and order["payment_method"] is None
        assert order["total_paise"] == order["subtotal_paise"] + order["tax_paise"] + order["fee_paise"]
        assert order["events"].keys() == {Status.PLACED}
    dosa = next(o for o in placed if o["outlet"] == "Pure Veg")
    assert dosa["subtotal_paise"] == 14000 and dosa["estimated_minutes"] == 10


def test_one_outlet_short_means_no_order_for_any_outlet(shop, aug4_1300):
    before = shop.order_count()
    with pytest.raises(AvailabilityError):
        shop.checkout("Asha", aug4_1300, {"Masala Dosa": 2, "Veg Sandwich": 13})  # Pure Veg fine, Fast Food short
    assert shop.order_count() == before
    assert shop.available(aug4_1300)["Masala Dosa"] == 15


def test_quantities_of_one_item_with_different_options_are_added_up_for_availability(shop, aug4_1300):
    fruit = shop.item("Fruit Bowl")  # 6 left
    with pytest.raises(AvailabilityError, match="requested 7, only 6 left"):
        orders.submit_order("Asha", aug4_1300, [
            {"item_id": fruit, "qty": 4, "options": ["Add yogurt"]},
            {"item_id": fruit, "qty": 3, "options": []},
        ], db_path=shop.db_path)


# --- Demo payment ------------------------------------------------------------------------------

def test_upi_marks_every_order_in_the_checkout_paid(shop, aug4_1300):
    checkout = shop.checkout("Asha", aug4_1300, {"Masala Dosa": 1, "Fruit Bowl": 1})
    paid = orders.pay(checkout.checkout_id, orders.UPI, "asha", db_path=shop.db_path)
    assert {(o["payment_method"], o["payment_status"]) for o in paid} == {("UPI", "Paid")}


def test_cash_on_delivery_is_collected_on_completion(shop, aug4_1300):
    checkout = shop.checkout("Asha", aug4_1300, {"Fruit Bowl": 1})
    orders.pay(checkout.checkout_id, orders.CASH, "Asha", db_path=shop.db_path)
    (order_id,) = checkout.order_ids
    assert orders.get_order(order_id, db_path=shop.db_path)["payment_status"] == "Pay at pickup"
    done = shop.staff(order_id, "accept", "start_preparing", "mark_ready", "deliver", "complete")
    assert (done["status"], done["payment_status"]) == (Status.COMPLETED, "Paid")


def test_payment_cannot_be_recorded_twice_or_by_someone_else(shop, aug4_1300):
    checkout = shop.checkout("Asha", aug4_1300, {"Fruit Bowl": 1})
    with pytest.raises(InvalidTransition, match="another customer"):
        orders.pay(checkout.checkout_id, orders.UPI, "Ben", db_path=shop.db_path)
    orders.pay(checkout.checkout_id, orders.UPI, "Asha", db_path=shop.db_path)
    with pytest.raises(InvalidTransition, match="already been recorded"):
        orders.pay(checkout.checkout_id, orders.CASH, "Asha", db_path=shop.db_path)
    with pytest.raises(ValidationError):
        orders.pay(checkout.checkout_id, "Card", "Asha", db_path=shop.db_path)
    with pytest.raises(NotFound):
        orders.pay("NOPE", orders.UPI, "Asha", db_path=shop.db_path)


@pytest.mark.parametrize("close", ["reject", "cancel"])
def test_upi_payment_is_refunded_when_the_order_is_rejected_or_cancelled(shop, aug4_1300, close):
    checkout = shop.checkout("Asha", aug4_1300, {"Fruit Bowl": 1})
    orders.pay(checkout.checkout_id, orders.UPI, "Asha", db_path=shop.db_path)
    (order_id,) = checkout.order_ids
    if close == "reject":
        result = shop.staff(order_id, "reject", reason="Out of fruit")
    else:
        shop.staff(order_id, "accept")
        result = shop.cancel(order_id, "Asha")
    assert result["payment_status"] == "Refunded"


# --- Preparation time --------------------------------------------------------------------------

def test_accept_sets_the_vendors_preparation_time(shop, aug4_1300):
    order_id = shop.order("Asha", aug4_1300, {"Fruit Bowl": 1})
    accepted = shop.staff(order_id, "accept", prep_minutes=25)
    assert (accepted["status"], accepted["prep_minutes"], accepted["estimated_minutes"]) == (Status.ACCEPTED, 25, 25)


def test_accept_without_a_time_uses_the_slowest_item(shop, aug4_1300):
    order_id = shop.order("Asha", aug4_1300, {"Veg Sandwich": 1})  # 8 minutes
    assert shop.staff(order_id, "accept")["prep_minutes"] == 8


@pytest.mark.parametrize("minutes", [0, 241, 2.5, "10"])
def test_invalid_preparation_time_is_refused(shop, aug4_1300, minutes):
    order_id = shop.order("Asha", aug4_1300, {"Fruit Bowl": 1})
    with pytest.raises(ValidationError):
        shop.staff(order_id, "accept", prep_minutes=minutes)
    assert shop.status(order_id) == Status.PLACED


def test_preparation_time_can_change_only_while_accepted_or_preparing(shop, aug4_1300):
    order_id = shop.order("Asha", aug4_1300, {"Fruit Bowl": 1})
    with pytest.raises(InvalidTransition):
        orders.set_prep_minutes(order_id, 20, db_path=shop.db_path)
    shop.staff(order_id, "accept", prep_minutes=10)
    assert orders.set_prep_minutes(order_id, 20, db_path=shop.db_path)["prep_minutes"] == 20
    shop.staff(order_id, "start_preparing")
    assert orders.set_prep_minutes(order_id, 30, db_path=shop.db_path)["prep_minutes"] == 30
    shop.staff(order_id, "mark_ready")
    with pytest.raises(InvalidTransition):
        orders.set_prep_minutes(order_id, 40, db_path=shop.db_path)


# --- Delivered and Completed -------------------------------------------------------------------

def test_timeline_records_every_step(shop, aug4_1300):
    order_id = shop.order("Asha", aug4_1300, {"Fruit Bowl": 1})
    done = shop.staff(order_id, "accept", "start_preparing", "mark_ready", "deliver", "complete")
    assert list(done["events"]) == [Status.PLACED, Status.ACCEPTED, Status.PREPARING, Status.READY,
                                    Status.DELIVERED, Status.COMPLETED]


def test_completed_order_cannot_change_and_cannot_be_delivered_again(shop, aug4_1300):
    order_id = shop.order("Asha", aug4_1300, {"Fruit Bowl": 1})
    shop.staff(order_id, "accept", "start_preparing", "mark_ready", "deliver", "complete")
    with pytest.raises(InvalidTransition, match="already been delivered"):
        shop.staff(order_id, "deliver")
    with pytest.raises(InvalidTransition, match="complete"):
        shop.staff(order_id, "complete")


def test_customer_cannot_cancel_a_delivered_order(shop, aug4_1300):
    order_id = shop.order("Asha", aug4_1300, {"Fruit Bowl": 1})
    shop.staff(order_id, "accept", "start_preparing", "mark_ready", "deliver")
    with pytest.raises(InvalidTransition):
        shop.cancel(order_id, "Asha")


# --- Reorder -------------------------------------------------------------------------------------

def test_reorder_repeats_items_quantities_and_options(shop, aug5_1300):
    sandwich = shop.item("Veg Sandwich")
    checkout = orders.submit_order("Asha", aug5_1300, [
        {"item_id": sandwich, "qty": 2, "options": ["Extra cheese", "No onion"]},
        {"item_id": shop.item("French Fries"), "qty": 1, "options": []},
    ], db_path=shop.db_path)
    (order_id,) = checkout.order_ids
    lines = orders.reorder_lines(order_id, db_path=shop.db_path)
    assert lines == [
        {"item_id": sandwich, "qty": 2, "options": ["Extra cheese", "No onion"]},
        {"item_id": shop.item("French Fries"), "qty": 1, "options": []},
    ]
    again = orders.submit_order("Asha", aug5_1300, lines, db_path=shop.db_path)
    assert orders.get_order(again.order_ids[0], db_path=shop.db_path)["total_paise"] == \
        orders.get_order(order_id, db_path=shop.db_path)["total_paise"]


def test_demo_customer_has_order_history_to_reorder_from(db_path):
    history = orders.list_orders(customer_name="Asha Rao", db_path=db_path)
    assert {o["status"] for o in history} == {Status.COMPLETED, Status.REJECTED, Status.PREPARING}
    completed = next(o for o in history if o["status"] == Status.COMPLETED)
    assert orders.reorder_lines(completed["id"], db_path=db_path)


# --- Vendor metrics ------------------------------------------------------------------------------

def test_vendor_metrics_follow_new_orders_and_status_changes(shop, aug4_1300):
    before = orders.vendor_metrics(db_path=shop.db_path)
    order_id = shop.order("Asha", aug4_1300, {"Fruit Bowl": 1})  # ₹90 + ₹4.50 GST + ₹5 fee
    after = orders.vendor_metrics(db_path=shop.db_path)
    assert after["orders_today"] == before["orders_today"] + 1
    assert after["pending"] == before["pending"] + 1
    assert after["revenue_paise"] == before["revenue_paise"] + 9950
    shop.staff(order_id, "reject", reason="test")
    rejected = orders.vendor_metrics(db_path=shop.db_path)
    assert rejected["revenue_paise"] == before["revenue_paise"]
    assert rejected["pending"] == before["pending"]


def test_vendor_metrics_per_outlet_and_day(shop, db_path):
    with db.connection(db_path) as conn:
        healthy = conn.execute("SELECT id FROM outlet WHERE name = 'Healthy Food'").fetchone()["id"]
    metrics = orders.vendor_metrics(outlet_id=healthy, db_path=db_path)
    assert metrics["pending"] == 1  # Priya Nair's seeded order
    assert orders.vendor_metrics(day=date(2026, 8, 3), db_path=db_path)["orders_today"] == 3  # history date
