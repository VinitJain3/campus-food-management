"""The real Streamlit screens, driven headlessly (AppTest) against a temporary database.

AppTest cannot follow st.navigation between function pages or keep a dialog open
across reruns, so each screen is rendered directly and dialog flows are covered
by the browser check in tools/browser_check.py.
"""

import pytest
from streamlit.testing.v1 import AppTest

from campus_food import db, orders
from campus_food.status import Status


@pytest.fixture(autouse=True)
def use_test_db(db_path, monkeypatch):
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_path)


def screen(name: str) -> AppTest:
    """Render one screen function from ui/ with fresh session state."""
    def script(screen_name):
        from ui import components, customer, theme, vendor  # noqa: F401
        components.init_state()
        {"orders": customer.orders_page, "vendor": vendor.dashboard_page, "tools": vendor.tools_page}[screen_name]()
    at = AppTest.from_function(script, args=(name,), default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_home_shows_five_outlets_and_opens_a_menu():
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    assert not at.exception
    assert [b.label for b in at.button if b.key and b.key.startswith("view-")] == ["View menu"] * 5
    at.button(key="view-2").click().run()  # Fast Food
    assert at.query_params["outlet"] in ("2", ["2"])
    assert sorted(b.key for b in at.button if b.key and b.key.startswith("add-")) == ["add-4", "add-5", "add-6"]


def test_menu_quantity_controls_update_the_cart(shop):
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    at.button(key="view-2").click().run()
    at.button(key="add-4").click().run()
    at.button(key="more-4").click().run()
    assert at.session_state["cart"] == [{"item_id": 4, "qty": 2, "options": []}]
    at.button(key="less-4").click().run()
    at.button(key="less-4").click().run()
    assert at.session_state["cart"] == []


def test_unavailable_dish_cannot_be_added():
    at = AppTest.from_file("../app.py", default_timeout=30).run()  # default slot: 4 Aug 13:00
    at.button(key="view-1").click().run()  # Coffee
    assert at.button(key="add-1").disabled  # Cold Coffee is unavailable on 4 Aug
    assert not at.button(key="add-2").disabled


def test_vendor_moves_an_order_forward(shop, aug5_1300):
    order_id = shop.order("Dev", aug5_1300, {"Veg Burger": 1})
    shop.staff(order_id, "accept", prep_minutes=10)
    at = screen("vendor")
    assert [m.label for m in at.metric] == ["Revenue today", "Today's orders", "Pending", "Completed today"]
    for action, expected in [("start_preparing", Status.PREPARING), ("mark_ready", Status.READY),
                             ("deliver", Status.DELIVERED), ("complete", Status.COMPLETED)]:
        at.button(key=f"{action}-{order_id}").click().run()
        assert not at.exception
        assert shop.status(order_id) == expected


def test_vendor_dashboard_offers_accept_and_reject_for_new_orders(shop, aug5_1300):
    order_id = shop.order("Dev", aug5_1300, {"Veg Burger": 1})
    at = screen("vendor")
    assert at.button(key=f"accept-{order_id}").label == "Accept"
    assert at.button(key=f"reject-{order_id}").label == "Reject"


def test_customer_cancels_an_accepted_order_with_confirmation(shop, aug5_1300):
    order_id = shop.order("Asha Rao", aug5_1300, {"Veg Burger": 1})
    shop.staff(order_id, "accept")
    at = screen("orders")
    at.button(key=f"cancel-{order_id}").click().run()
    assert shop.status(order_id) == Status.ACCEPTED  # asks first
    at.button(key=f"cancel-yes-{order_id}").click().run()
    assert shop.status(order_id) == Status.CANCELLED


def test_reorder_puts_previous_items_in_the_cart(db_path):
    completed = next(o for o in orders.list_orders(customer_name="Asha Rao", db_path=db_path)
                     if o["status"] == Status.COMPLETED)
    at = screen("orders")
    at.button(key=f"reorder-{completed['id']}").click().run()
    assert sorted((line["item_id"], line["qty"]) for line in at.session_state["cart"]) == \
        sorted((item["item_id"], item["qty"]) for item in completed["items"])


def test_stock_page_and_reset(shop, aug4_1300):
    shop.order("Asha", aug4_1300, {"Fruit Bowl": 6})
    at = screen("tools")
    assert at.dataframe[0].value.shape[0] == 15  # every dish
    at.checkbox(key="reset-sure").check().run()
    at.button(key="reset").click().run()
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6 and shop.order_count() == 12
