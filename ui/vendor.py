"""Vendor screens: order dashboard (accept, reject, prepare, hand over) and stock & tools."""

from datetime import date

import streamlit as st

from campus_food import db, inventory, orders
from campus_food.errors import BusinessError
from campus_food.status import Status

from . import components as ui
from .components import esc, money

QUICK_REASONS = ["Item ran out", "Kitchen at capacity", "Outlet closing early", "Ingredient shortage"]
NEXT_STEP = {
    Status.ACCEPTED: ("start_preparing", "Start preparing", ":material/skillet:"),
    Status.PREPARING: ("mark_ready", "Mark ready", ":material/notifications_active:"),
    Status.READY: ("deliver", "Mark delivered", ":material/takeout_dining:"),
    Status.DELIVERED: ("complete", "Complete order", ":material/task_alt:"),
}
TABS = [
    ("New", [Status.PLACED]),
    ("In kitchen", [Status.ACCEPTED, Status.PREPARING]),
    ("Ready", [Status.READY]),
    ("Handed over", [Status.DELIVERED]),
    ("Closed", [Status.COMPLETED, Status.REJECTED, Status.CANCELLED]),
]


def vendor_header(title: str, subtitle: str) -> int | None:
    with db.connection() as conn:
        outlets = {outlet["id"]: outlet for outlet in inventory.list_outlets(conn)}
    selected = st.session_state.vendor_outlet
    name = outlets[selected]["name"] if selected in outlets else "All outlets"
    st.html(f"<div class='vendor-banner'><div><p class='eyebrow' style='color:#99F6E4'>Vendor console · {esc(name)}</p>"
            f"<h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>"
            f"<span class='chip solid-teal'>{date.today():%a %d %b %Y}</span></div>")
    pick, refresh = st.columns([3, 1], vertical_alignment="bottom")
    with pick:
        ui.bound(st.selectbox, "Outlet", "vendor_outlet", "w-vendor-outlet", options=[ui.ALL_OUTLETS, *outlets],
                 format_func=lambda oid: "All outlets" if oid == ui.ALL_OUTLETS else f"{outlets[oid]['emoji']} {outlets[oid]['name']}")
    with refresh.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Refresh", icon=":material/refresh:", key="vendor-refresh"):
            st.rerun()
    return None if st.session_state.vendor_outlet == ui.ALL_OUTLETS else st.session_state.vendor_outlet


def dashboard_page() -> None:
    outlet_id = vendor_header("Orders", "Accept new orders, set preparation times and move them to the counter.")
    metrics = orders.vendor_metrics(outlet_id=outlet_id)
    for column, (label, value, help_text) in zip(st.columns(4), [
        ("Revenue today", money(metrics["revenue_paise"]), "Orders placed today, excluding rejected and cancelled"),
        ("Today's orders", metrics["orders_today"], "Orders placed today"),
        ("Pending", metrics["pending"], "New orders waiting to be accepted or rejected"),
        ("Completed today", metrics["completed_today"], "Today's orders handed over (Delivered or Completed)"),
    ]):
        column.metric(label, value, help=help_text)

    everything = orders.list_orders(outlet_id=outlet_id)
    tabs = st.tabs([f"{label} ({sum(1 for o in everything if o['status'] in statuses)})" for label, statuses in TABS])
    for tab, (label, statuses) in zip(tabs, TABS):
        with tab:
            group = [order for order in everything if order["status"] in statuses]
            if not group:
                ui.empty_state("✨", f"Nothing in {label.lower()}", "New orders appear here as customers place them.")
            for order in sorted(group, key=lambda o: o["id"], reverse=label == "Closed"):
                vendor_order_card(order)


def vendor_order_card(order: dict) -> None:
    order_id = order["id"]
    with st.container(key=f"card-vorder-{order_id}"):
        head, side = st.columns([3, 2], vertical_alignment="top")
        with head:
            phone = f" · 📞 {esc(order['customer_phone'])}" if order["customer_phone"] else ""
            st.html(
                f"<div style='display:flex;gap:.8rem;align-items:center'>"
                + ui.tile(order["outlet_emoji"], order["colour_a"], order["colour_b"], size="sm", label=order["outlet"])
                + f"<div><h3>#{order_id} · {esc(order['customer_name'])}</h3>"
                f"<div class='meta'><span>{esc(order['outlet'])}{phone}</span></div>"
                f"<div class='meta'><span>Ordered {ui.when(order['created_at'])} "
                f"({orders.minutes_since(order['created_at'])} min ago)</span>"
                f"<span>Pickup <b>{esc(order['slot_label'])}</b></span></div></div></div>"
            )
        with side:
            with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
                ui.status_badge(order["status"])
                st.html(f"<span class='money' style='font-size:1.2rem'>{money(order['total_paise'])}</span>", width="content")
            st.html(f"<div style='text-align:right'>{ui.payment_chip(order)}</div>")
        st.html(ui.lines_table(order["items"]))
        bill, prep = st.columns([3, 2], vertical_alignment="top")
        bill.html(ui.bill_html(order["subtotal_paise"], order["tax_paise"], order["fee_paise"], order["total_paise"]))
        with prep:
            if order["status"] == Status.PLACED:
                st.html(f"<p class='muted'>Suggested prep time <b>{order['estimated_minutes']} min</b> (slowest dish).</p>")
            elif order["prep_minutes"]:
                st.html(f"<p class='muted'>Prep time set to <b>{order['prep_minutes']} min</b>.</p>")
            if order["reason"] and order["status"] in (Status.REJECTED, Status.CANCELLED, Status.ACCEPTED):
                st.html(f"<p class='muted'><b>Note:</b> {esc(order['reason'])}</p>")
        vendor_actions(order)


def vendor_actions(order: dict) -> None:
    order_id, status = order["id"], order["status"]
    with st.container(horizontal=True, gap="small"):
        if status == Status.PLACED:
            if st.button("Accept", key=f"accept-{order_id}", type="primary", icon=":material/check:"):
                accept_dialog(order)
            if st.button("Reject", key=f"reject-{order_id}", icon=":material/block:"):
                reject_dialog(order)
        elif status in NEXT_STEP:
            action, label, icon = NEXT_STEP[status]
            if status == Status.DELIVERED and order["payment_status"] == "Pay at pickup":
                label = f"Collect {money(order['total_paise'])} cash & complete"
            if st.button(label, key=f"{action}-{order_id}", type="primary", icon=icon):
                run(lambda: orders.transition(order_id, action, orders.STAFF),
                    lambda done: f"Order #{order_id} is now {done['status']}.")
            if status in (Status.ACCEPTED, Status.PREPARING):
                with st.popover("Prep time", icon=":material/timer:"):
                    minutes = st.number_input("Minutes", min_value=orders.MIN_PREP_MINUTES,
                                              max_value=orders.MAX_PREP_MINUTES, step=1,
                                              value=order["prep_minutes"] or order["estimated_minutes"],
                                              key=f"prep-edit-{order_id}")
                    if st.button("Update prep time", key=f"prep-save-{order_id}", type="primary"):
                        run(lambda: orders.set_prep_minutes(order_id, int(minutes)),
                            f"Order #{order_id}: prep time set to {int(minutes)} min.")


def run(action, success) -> None:
    try:
        result = action()
    except BusinessError as exc:
        ui.flash(exc.message, "⚠️")
    else:
        ui.flash(success(result) if callable(success) else success, "✅")
    st.rerun()


@st.dialog("Accept order")
def accept_dialog(order: dict) -> None:
    st.html(f"<p><b>#{order['id']}</b> · {esc(order['customer_name'])} · {esc(order['outlet'])}</p>"
            + ui.lines_table(order["items"]))
    minutes = st.number_input("Expected preparation time (minutes)", min_value=orders.MIN_PREP_MINUTES,
                              max_value=orders.MAX_PREP_MINUTES, value=order["estimated_minutes"], step=1,
                              key=f"accept-minutes-{order['id']}",
                              help="The customer sees this on their order. You can change it later.")
    if st.button(f"Accept · ready in {int(minutes)} min", type="primary", icon=":material/check:", width="stretch",
                 key=f"accept-confirm-{order['id']}"):
        run(lambda: orders.transition(order["id"], "accept", orders.STAFF, prep_minutes=int(minutes)),
            f"Order #{order['id']} accepted · ready in {int(minutes)} min.")


@st.dialog("Reject order")
def reject_dialog(order: dict) -> None:
    st.html(f"<p><b>#{order['id']}</b> · {esc(order['customer_name'])} · {money(order['total_paise'])}</p>"
            "<p class='muted'>The customer sees this reason. All reserved items go back on sale immediately.</p>")
    quick = st.pills("Common reasons", QUICK_REASONS, key=f"reject-quick-{order['id']}")
    reason = st.text_area("Reason (required)", value=quick or "", key=f"reject-reason-{order['id']}-{quick}",
                          placeholder="Tell the customer why", max_chars=200)
    if st.button("Reject order", type="primary", icon=":material/block:", width="stretch",
                 disabled=not reason.strip(), key=f"reject-confirm-{order['id']}"):
        run(lambda: orders.transition(order["id"], "reject", orders.STAFF, reason=reason),
            f"Order #{order['id']} rejected. Its items are back on sale.")


def tools_page() -> None:
    outlet_id = vendor_header("Stock & tools", "Live availability per pickup slot, hand-over by order number and demo reset.")
    with db.connection() as conn:
        slots = [slot for slot in inventory.list_slots(conn, orderable_only=True)]
        dates = sorted({slot["slot_date"] for slot in slots})
        day = st.segmented_control("Pickup date", dates, default=dates[0], key="stock-date",
                                   format_func=lambda d: date.fromisoformat(d).strftime("%a %d %b"),
                                   required=True)
        table = {}
        for slot in [s for s in slots if s["slot_date"] == day]:
            column = f"{slot['start_time']}–{slot['end_time']}"
            for item in inventory.get_availability(conn, slot["id"]):
                if outlet_id not in (None, item.outlet_id):
                    continue
                row = table.setdefault(item.name, {"Dish": item.name, "Outlet": item.outlet})
                row[column] = ("Unavailable" if item.state == inventory.RESTRICTED
                               else f"{item.available} / {item.capacity}")
    with st.container(key="panel-stock"):
        st.html("<h3 style='margin-top:0'>Availability by slot</h3>")
        st.dataframe(list(table.values()), hide_index=True, width="stretch")
        st.caption("Units left / quantity per slot. Rejected and cancelled orders no longer count; "
                   "delivered and completed orders do (the food has been used).")

    hand, reset = st.columns(2, gap="large")
    with hand.container(key="panel-handover"):
        st.html("<h3 style='margin-top:0'>Hand over by order number</h3>")
        number = st.number_input("Order number", min_value=1, step=1, value=None, placeholder="e.g. 13",
                                 key="handover-number")
        if st.button("Mark delivered", icon=":material/takeout_dining:", type="primary", disabled=number is None,
                     key="handover"):
            run(lambda: orders.transition(int(number), "deliver", orders.STAFF), f"Order #{number} delivered.")
    with reset.container(key="panel-reset"):
        st.html("<h3 style='margin-top:0'>Demo data</h3>")
        sure = st.checkbox("Delete all orders and reload the challenge data", key="reset-sure")
        if st.button("Reset demo data", icon=":material/restart_alt:", disabled=not sure, key="reset"):
            db.reset_db()
            st.session_state.cart = []
            st.session_state.checkout = None
            ui.flash("Demo data reset to the challenge figures.", "🔄")
            st.rerun()
