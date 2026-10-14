"""End-to-end through the real Streamlit UI (headless AppTest), against a temporary database."""

import pytest
from streamlit.testing.v1 import AppTest

from campus_food import db, orders
from campus_food.status import Status


@pytest.fixture
def app(db_path, monkeypatch):
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_path)
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception
    return at


def as_customer(at, name):
    at.sidebar.radio[0].set_value("Customer").run()
    at.sidebar.text_input(key="customer_name").input(name).run()


def as_staff(at):
    at.sidebar.radio[0].set_value("Outlet staff").run()


def choose_slot(at, shop, slot_date, start):
    at.selectbox[0].set_value(shop.slot(slot_date, start)).run()


def set_qty(at, shop, item_name, qty):
    version = at.session_state["cart_version"]
    at.number_input(key=f"qty_{version}_{shop.item(item_name)}").set_value(qty)


def submit(at):
    next(b for b in at.button if b.label == "Submit pre-order").click().run()


def click(at, key):
    at.button(key=key).click().run()


def test_customer_and_staff_end_to_end(app, shop, aug4_1300):
    at = app
    # Customer: order 2 Masala Dosa + 1 Fruit Bowl for 4 Aug 13:00.
    as_customer(at, "Asha")
    choose_slot(at, shop, "2026-08-04", "13:00")
    set_qty(at, shop, "Masala Dosa", 2)
    set_qty(at, shop, "Fruit Bowl", 1)
    submit(at)
    assert not at.exception
    assert "Order #4 submitted" in at.success[0].value
    assert shop.available(aug4_1300)["Fruit Bowl"] == 5
    assert at.session_state["cart_version"] == 1  # cart cleared after success

    # Staff: confirm, start preparing, mark ready, collect.
    as_staff(at)
    for key, expected in [("confirm_4", Status.CONFIRMED), ("start_preparing_4", Status.PREPARING),
                          ("mark_ready_4", Status.READY)]:
        click(at, key)
        assert not at.exception
        assert shop.status(4) == expected

    # Customer sees the status and cannot cancel any more.
    as_customer(at, "Asha")
    assert any("Ready for Pickup" in md.value for md in at.markdown)
    assert not [b for b in at.button if b.key == "cancel_4"]

    as_staff(at)
    click(at, "collect_4")
    assert shop.status(4) == Status.COLLECTED
    # Collecting the same order again from the "collect by number" tab is refused.
    at.number_input[0].set_value(4).run()
    next(b for b in at.button if b.label == "Mark collected").click().run()
    assert "already been collected" in at.error[0].value


def test_all_or_nothing_failure_is_shown_and_cart_kept(app, shop, aug4_1300):
    at = app
    as_customer(at, "Asha")
    choose_slot(at, shop, "2026-08-04", "13:00")
    set_qty(at, shop, "Fruit Bowl", 6)
    set_qty(at, shop, "Veg Sandwich", 13)
    submit(at)
    assert "Veg Sandwich: requested 13, only 12 left." in at.error[0].value
    assert shop.order_count() == 3  # only the seed orders
    assert at.session_state["cart_version"] == 0  # cart kept so the customer can adjust it


def test_reject_and_customer_cancel_release_stock(app, shop, aug4_1300):
    at = app
    first = shop.order("Asha", aug4_1300, {"Fruit Bowl": 6})
    as_staff(at)
    click(at, f"reject_{first}")
    assert "Give a reason" in at.error[0].value  # reason is required
    at.text_input(key=f"reason_{first}").input("Out of fruit").run()
    click(at, f"reject_{first}")
    assert shop.status(first) == Status.REJECTED
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6

    second = shop.order("Ben", aug4_1300, {"Fruit Bowl": 2})
    shop.staff(second, "confirm")
    as_customer(at, "Ben")
    click(at, f"cancel_{second}")
    assert shop.status(second) == Status.CANCELLED
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6


def test_reset_button_restores_seed(app, shop, aug4_1300):
    at = app
    shop.order("Asha", aug4_1300, {"Fruit Bowl": 6})
    as_staff(at)
    at.sidebar.checkbox[0].check().run()
    next(b for b in at.sidebar.button if b.label == "Reset demo data").click().run()
    assert shop.order_count() == 3
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6
    assert orders.list_orders(customer_name="Asha", db_path=shop.db_path) == []
