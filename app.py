"""Streamlit UI for the Campus Food Pre-Order and Pickup Management System.

Run with:  streamlit run app.py

This file holds no business rules. Every decision (availability, validation,
status changes) is made in campus_food/ and arrives here as a result or a
BusinessError whose message is shown as-is.
"""

import streamlit as st

from campus_food import db, inventory, orders
from campus_food.errors import BusinessError
from campus_food.status import Status

st.set_page_config(page_title="Campus Food Pre-Order", page_icon="🍱", layout="wide")

STATUS_COLOURS = {
    Status.SUBMITTED: "orange",
    Status.CONFIRMED: "blue",
    Status.PREPARING: "violet",
    Status.READY: "green",
    Status.COLLECTED: "gray",
    Status.REJECTED: "red",
    Status.CANCELLED: "gray",
}
ACTIVE_STATUSES = [Status.SUBMITTED, Status.CONFIRMED, Status.PREPARING, Status.READY]


@st.cache_resource
def start_up() -> bool:
    db.init_db()  # creates the schema; seeds only an empty database
    return True


# --- Small UI helpers ---------------------------------------------------------------------------

def flash(kind: str, text: str) -> None:
    st.session_state["flash"] = (kind, text)


def show_flash() -> None:
    if "flash" in st.session_state:
        kind, text = st.session_state.pop("flash")
        (st.success if kind == "success" else st.error)(text)


def run(action, success_message, on_success=None) -> None:
    """Call the core, turn the outcome into a message, and redraw the page."""
    try:
        result = action()
    except BusinessError as exc:
        flash("error", exc.message)
    else:
        flash("success", success_message(result) if callable(success_message) else success_message)
        if on_success:
            on_success()
    st.rerun()


def load_slots():
    with db.connection() as conn:
        return {slot["id"]: inventory.slot_label(slot) for slot in inventory.list_slots(conn)}


def load_outlets():
    with db.connection() as conn:
        return {outlet["id"]: outlet["name"] for outlet in inventory.list_outlets(conn)}


def availability_text(item: inventory.ItemAvailability) -> str:
    if item.state == inventory.RESTRICTED:
        return f":red[Unavailable: {item.restriction}]"
    if item.state == inventory.SOLD_OUT:
        return ":red[Sold out]"
    return f"{item.available} of {item.capacity} left"


def status_badge(status: str) -> str:
    return f":{STATUS_COLOURS[status]}[**{status}**]"


def order_summary(order: dict) -> None:
    st.markdown(f"#### Order #{order['id']} · {status_badge(order['status'])}")
    st.caption(f"{order['customer_name']} · pickup {order['slot_label']}")
    st.markdown("  \n".join(f"{line['qty']} × {line['name']} ({line['outlet']})" for line in order["items"]))
    if order["reason"]:
        st.caption(f"Reason: {order['reason']}")


# --- Customer -------------------------------------------------------------------------------------

def customer_page(customer_name: str) -> None:
    st.header("Pre-order food for pickup")
    slots = load_slots()
    slot_id = st.selectbox("Pickup slot", list(slots), format_func=slots.get)

    with db.connection() as conn:
        items = inventory.get_availability(conn, slot_id)

    # Bumping the version gives the quantity inputs new keys, which clears the cart after a successful order.
    version = st.session_state.setdefault("cart_version", 0)
    quantities = {}
    with st.form("order_form"):
        widths = [3, 2, 2, 3, 2]
        for column, title in zip(st.columns(widths), ["Item", "Outlet", "Category", "Availability", "Quantity"]):
            column.markdown(f"**{title}**")
        for item in items:
            cols = st.columns(widths, vertical_alignment="center")
            cols[0].write(item.name)
            cols[1].write(item.outlet)
            cols[2].write(item.category)
            cols[3].markdown(availability_text(item))
            quantities[item.item_id] = cols[4].number_input(
                f"Quantity of {item.name}", min_value=0, step=1, value=0,
                key=f"qty_{version}_{item.item_id}", label_visibility="collapsed",
            )
        st.caption("Your whole order must be available for the chosen slot. Nothing is reserved unless every item fits.")
        submitted = st.form_submit_button("Submit pre-order", type="primary")

    if submitted:
        cart = {item_id: qty for item_id, qty in quantities.items() if qty}

        def clear_cart():
            st.session_state["cart_version"] = version + 1

        run(
            lambda: orders.submit_order(customer_name, slot_id, cart),
            lambda order_id: f"Order #{order_id} submitted for {slots[slot_id]}. It is waiting for outlet confirmation.",
            on_success=clear_cart,
        )

    st.subheader("My orders")
    if not customer_name.strip():
        st.info("Enter your name in the sidebar to place orders and see their status.")
        return
    my_orders = orders.list_orders(customer_name=customer_name)
    if not my_orders:
        st.write("No orders yet.")
    for order in my_orders:
        with st.container(border=True):
            order_summary(order)
            if order["status"] == Status.CONFIRMED:
                if st.button("Cancel order", key=f"cancel_{order['id']}"):
                    run(
                        lambda: orders.transition(order["id"], "cancel", orders.CUSTOMER, actor_name=customer_name),
                        f"Order #{order['id']} cancelled. Its items are available again.",
                    )
            elif order["status"] in (Status.PREPARING, Status.READY):
                st.caption("Preparation has started, so this order can no longer be cancelled.")
            elif order["status"] == Status.SUBMITTED:
                st.caption("Waiting for the outlet to confirm.")


# --- Outlet staff --------------------------------------------------------------------------------

STAFF_BUTTONS = {
    Status.CONFIRMED: ("start_preparing", "Start preparing"),
    Status.PREPARING: ("mark_ready", "Mark ready for pickup"),
    Status.READY: ("collect", "Mark collected"),
}


def staff_order_card(order: dict) -> None:
    with st.container(border=True):
        order_summary(order)
        order_id = order["id"]
        if order["status"] == Status.SUBMITTED:
            confirm_col, reason_col, reject_col = st.columns([1, 2, 1], vertical_alignment="bottom")
            if confirm_col.button("Confirm", key=f"confirm_{order_id}", type="primary"):
                run(lambda: orders.transition(order_id, "confirm", orders.STAFF), f"Order #{order_id} confirmed.")
            reason = reason_col.text_input("Rejection reason", key=f"reason_{order_id}")
            if reject_col.button("Reject", key=f"reject_{order_id}"):
                run(
                    lambda: orders.transition(order_id, "reject", orders.STAFF, reason=reason),
                    f"Order #{order_id} rejected. Its items are available again.",
                )
        elif order["status"] in STAFF_BUTTONS:
            action, label = STAFF_BUTTONS[order["status"]]
            if st.button(label, key=f"{action}_{order_id}", type="primary"):
                run(
                    lambda: orders.transition(order_id, action, orders.STAFF),
                    lambda updated: f"Order #{order_id} is now {updated['status']}.",
                )


def staff_page(outlet_id: int | None) -> None:
    st.header("Outlet staff")
    if st.button("Refresh"):
        st.rerun()
    slots = load_slots()
    queue_tab, stock_tab, collect_tab = st.tabs(["Order queue", "Availability by slot", "Collect by order number"])

    with queue_tab:
        filter_slot, filter_status = st.columns(2)
        slot_id = filter_slot.selectbox(
            "Pickup slot", [None, *slots], format_func=lambda s: "All slots" if s is None else slots[s]
        )
        statuses = filter_status.multiselect("Status", list(STATUS_COLOURS), default=ACTIVE_STATUSES)
        queue = orders.list_orders(slot_id=slot_id, statuses=statuses or None, outlet_id=outlet_id)
        if not queue:
            st.write("No orders match these filters.")
        for status in STATUS_COLOURS:
            group = [order for order in queue if order["status"] == status]
            if group:
                st.subheader(f"{status} ({len(group)})")
                for order in reversed(group):  # oldest first within a status
                    staff_order_card(order)

    with stock_tab:
        rows = {}
        with db.connection() as conn:
            for sid, label in slots.items():
                for item in inventory.get_availability(conn, sid):
                    row = rows.setdefault(item.name, {"Item": item.name, "Outlet": item.outlet})
                    if item.state == inventory.RESTRICTED:
                        row[label] = "Unavailable"
                    else:
                        row[label] = f"{item.available} / {item.capacity}"
        outlet_name = load_outlets().get(outlet_id)
        table = [row for row in rows.values() if outlet_name is None or row["Outlet"] == outlet_name]
        st.dataframe(table, hide_index=True, width="stretch")
        st.caption("Units left / quantity per slot. Rejected and cancelled orders no longer count.")

    with collect_tab:
        number = st.number_input("Order number", min_value=1, step=1, value=None, placeholder="e.g. 4")
        if st.button("Mark collected", disabled=number is None):
            run(lambda: orders.transition(int(number), "collect", orders.STAFF), f"Order #{number} collected.")


# --- Page -------------------------------------------------------------------------------------------

start_up()

with st.sidebar:
    st.title("🍱 Campus Food")
    role = st.radio("I am", ["Customer", "Outlet staff"])
    if role == "Customer":
        customer_name = st.text_input("Your name", key="customer_name")
    else:
        outlets = load_outlets()
        selected_outlet = st.selectbox(
            "Outlet", [None, *outlets], format_func=lambda o: "All outlets" if o is None else outlets[o]
        )
        st.divider()
        st.caption("Demo data")
        sure = st.checkbox("Delete all orders and reload the challenge data")
        if st.button("Reset demo data", disabled=not sure):
            db.reset_db()
            flash("success", "Demo data reset.")
            st.rerun()
    st.caption("No login in this prototype: the role switch and name are for demonstration only.")

show_flash()
if role == "Customer":
    customer_page(customer_name)
else:
    staff_page(selected_outlet)
