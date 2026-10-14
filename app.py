"""Campus Bites: Streamlit entry point for the Campus Food Pre-Order and Pickup Management System.

Run with:  streamlit run app.py

This file only wires up navigation. Screens live in ui/, and every business
decision (availability, pricing, validation, status changes) is made in
campus_food/ and arrives in the UI as a result or a BusinessError message.
"""

from pathlib import Path

import streamlit as st

from campus_food import db
from ui import components as ui
from ui import customer, theme, vendor

ASSETS = Path(__file__).resolve().parent / "assets"

st.set_page_config(page_title="Campus Bites · campus food pre-orders", page_icon=str(ASSETS / "icon.svg"),
                   layout="wide", initial_sidebar_state="collapsed")


@st.cache_resource
def start_up() -> bool:
    db.init_db()  # creates the schema; seeds only an empty database
    return True


def in_mode(mode: str, screen):
    """Each page belongs to a mode. Opening a page from the other mode switches
    the header (navigation links, colours) to that mode. The Outlets page is
    always the default (served at /), so every page keeps a stable URL."""
    def run_page():
        if st.session_state.mode != mode:
            st.session_state.mode = mode
            st.rerun()
        screen()
    run_page.__name__ = screen.__name__
    return run_page


start_up()
ui.init_state()
mode = st.session_state.mode
customer_mode = mode == "customer"
count = ui.cart_count()

pages = {
    "outlets": st.Page(in_mode("customer", customer.outlets_page), url_path="outlets", default=True,
                       title="Outlets" if customer_mode else "Customer app",
                       icon=":material/storefront:" if customer_mode else ":material/swap_horiz:"),
    "cart": st.Page(in_mode("customer", customer.cart_page), url_path="cart",
                    title=f"Cart ({count})" if count else "Cart", icon=":material/shopping_bag:",
                    visibility="visible" if customer_mode else "hidden"),
    "orders": st.Page(in_mode("customer", customer.orders_page), url_path="my-orders", title="My Orders",
                      icon=":material/receipt_long:", visibility="visible" if customer_mode else "hidden"),
    "vendor": st.Page(in_mode("vendor", vendor.dashboard_page), url_path="vendor",
                      title="Vendor mode" if customer_mode else "Orders",
                      icon=":material/swap_horiz:" if customer_mode else ":material/dashboard:"),
    "tools": st.Page(in_mode("vendor", vendor.tools_page), url_path="vendor-stock", title="Stock & tools",
                     icon=":material/inventory_2:", visibility="hidden" if customer_mode else "visible"),
}
ui.PAGES.update(pages)
order = ["outlets", "cart", "orders", "vendor", "tools"] if customer_mode else ["vendor", "tools", "outlets", "cart", "orders"]

st.logo(str(ASSETS / "logo.svg"), size="large")
theme.inject(vendor=not customer_mode)
current = st.navigation([pages[key] for key in order], position="top")
ui.show_flash()
current.run()
