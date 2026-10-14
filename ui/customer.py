"""Customer screens: outlets, menu, dish details, cart, payment, confirmation and My Orders."""

import time

import streamlit as st

from campus_food import db, inventory, orders, pricing
from campus_food.errors import BusinessError
from campus_food.status import Status

from . import components as ui
from .components import esc, money

DIET_FILTERS = ["Veg", "Vegan", "Gluten-free", "High protein"]


# --- Header strip shared by customer pages ------------------------------------------------------

def profile_bar(title: str, eyebrow: str) -> None:
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    left.html(f"<p class='eyebrow'>{esc(eyebrow)}</p><h1 style='margin:0;padding:0'>{esc(title)}</h1>")
    with right.container(horizontal=True, horizontal_alignment="right"):
        with st.popover(st.session_state.customer_name or "Your details", icon=":material/account_circle:",
                        help="Who is ordering. Demo only: there is no login."):
            ui.bound(st.text_input, "Name for pickup", "customer_name", "w-name", max_chars=60)
            ui.bound(st.text_input, "Phone", "customer_phone", "w-phone", max_chars=20)
            st.caption("Your name is how the counter finds your order. No login in this prototype.")


# --- Outlets and menu ---------------------------------------------------------------------------

def outlets_page() -> None:
    outlet_param = st.query_params.get("outlet")
    if outlet_param and outlet_param.isdigit():
        menu_view(int(outlet_param))
        return

    slot_id = st.session_state.slot_id
    with db.connection() as conn:
        outlet_rows = inventory.list_outlets(conn)
        menu = inventory.list_menu(conn)
    stock = ui.availability_map(slot_id)
    open_dishes = sum(1 for item in stock.values() if item.state == inventory.AVAILABLE)
    name = (st.session_state.customer_name or "there").split()[0]

    hero, side = st.columns([3, 2], gap="medium", vertical_alignment="center")
    hero.html(
        f"<div class='hero'><p class='eyebrow'>Hi {esc(name)} · campus pre-orders</p>"
        "<h1>Skip the queue.<br>Pick up when it's hot.</h1>"
        "<p>Order from any of the five campus outlets, choose a 30-minute pickup slot, and collect at the counter.</p>"
        f"<div class='stats'><span><b>5</b> outlets</span><span><b>{len(menu)}</b> dishes</span>"
        f"<span><b>{open_dishes}</b> available for your slot</span></div></div>"
    )
    with side.container(key="panel-pickup"):
        st.html("<p class='eyebrow'>When will you pick up?</p>")
        ui.slot_picker("pick-slot-home")
        st.caption("Availability on every card follows this slot. You can change it again at checkout.")
        if ui.cart_count():
            st.page_link(ui.PAGES["cart"], label=f"Go to cart · {ui.cart_count()} items", icon=":material/shopping_bag:")

    st.html("<h2 style='margin:1.6rem 0 .4rem'>Outlets on campus</h2>")
    for start in range(0, len(outlet_rows), 3):
        columns = st.columns(3, gap="medium")
        for column, outlet in zip(columns, outlet_rows[start:start + 3]):
            with column:
                outlet_card(outlet, [item for item in stock.values() if item.outlet_id == outlet["id"]])


def outlet_state(items) -> tuple[str, str]:
    open_items = [item for item in items if item.state == inventory.AVAILABLE]
    if not open_items:
        return "Not taking orders for this slot", "bad"
    if len(open_items) < len(items) or any(item.available <= inventory.LOW_STOCK for item in open_items):
        return "Limited menu", "warn"
    return "Accepting orders", "ok"


def outlet_card(outlet: dict, items) -> None:
    label, kind = outlet_state(items)
    with st.container(key=f"card-outlet-{outlet['id']}"):
        st.html(ui.tile(outlet["emoji"], outlet["colour_a"], outlet["colour_b"], chip_html=ui.chip(label, kind),
                        label=f"{outlet['name']} outlet"))
        st.html(
            f"<h3>{esc(outlet['name'])}</h3>"
            f"<div class='meta'><span>{esc(outlet['cuisine'])}</span></div>"
            f"<div class='meta'><span>★ <b>{outlet['rating']:.1f}</b> ({outlet['reviews']})</span>"
            f"<span>🕒 {outlet['opens']}–{outlet['closes']}</span></div>"
            f"<p class='desc'>{esc(outlet['tagline'])}</p>"
        )
        if st.button("View menu", key=f"view-{outlet['id']}", icon=":material/restaurant_menu:", type="primary",
                     width="stretch", help=f"Open the {outlet['name']} menu"):
            st.query_params["outlet"] = str(outlet["id"])
            st.rerun()


def menu_view(outlet_id: int) -> None:
    try:
        with db.connection() as conn:
            outlet = inventory.get_outlet(conn, outlet_id)
            items = inventory.list_menu(conn, outlet_id)
    except BusinessError:
        st.query_params.clear()
        st.rerun()

    if st.button("All outlets", icon=":material/arrow_back:", type="tertiary", key="back-to-outlets"):
        st.query_params.clear()
        st.rerun()
    label, kind = outlet_state([item for item in ui.availability_map(st.session_state.slot_id).values()
                                if item.outlet_id == outlet_id])
    st.html(
        f"<div class='banner' style='--a:{outlet['colour_a']};--b:{outlet['colour_b']}'>"
        f"<span class='big' aria-hidden='true'>{outlet['emoji']}</span><div>"
        f"<h1>{esc(outlet['name'])}</h1><p>{esc(outlet['cuisine'])} · {esc(outlet['tagline'])}</p>"
        f"<p>★ {outlet['rating']:.1f} ({outlet['reviews']} ratings) · Open {outlet['opens']}–{outlet['closes']} "
        f"&nbsp;{ui.chip(label, kind)}</p></div></div>"
    )

    filters, slot_col = st.columns([3, 2], vertical_alignment="bottom")
    with filters:
        chosen = st.pills("Dietary filter", DIET_FILTERS, selection_mode="multi", key=f"diet-{outlet_id}")
    with slot_col:
        slot_id = ui.slot_picker("pick-slot-menu")
    stock = ui.availability_map(slot_id)
    shown = [item for item in items if all(tag in item["tags"] for tag in chosen)]
    if not shown:
        ui.empty_state("🥄", "No dishes match these filters", "Clear a filter to see the full menu.")
        return
    for start in range(0, len(shown), 3):
        columns = st.columns(3, gap="medium")
        for column, item in zip(columns, shown[start:start + 3]):
            with column:
                item_card(item, outlet, stock[item["id"]])


def item_card(item: dict, outlet: dict, availability: inventory.ItemAvailability) -> None:
    in_cart = ui.cart_qty_for(item["id"])
    can_add = availability.state == inventory.AVAILABLE and in_cart < availability.available
    colour_a, colour_b = ui.item_colours(outlet)
    with st.container(key=f"card-item-{item['id']}"):
        st.html(ui.tile(item["emoji"], colour_a, colour_b, chip_html=ui.availability_chip(availability),
                        dim=availability.state != inventory.AVAILABLE, label=item["name"]))
        st.html(
            f"<div class='price-row'><h3>{esc(item['name'])}</h3><span class='money'>{money(item['price_paise'])}</span></div>"
            f"<p class='desc'>{esc(item['description'])}</p>"
            f"<div class='meta'><span>⏱ {item['prep_minutes']} min</span><span>{esc(item['category'])}</span></div>"
            + ui.tags_html(item["tags"])
        )
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            if in_cart:
                st.button(":material/remove:", key=f"less-{item['id']}", help=f"One less {item['name']}",
                          on_click=ui.cart_change, args=(item["id"], -1))
                st.html(f"<span class='money' aria-live='polite'>{in_cart} in cart</span>", width="content")
                st.button(":material/add:", key=f"more-{item['id']}", help=f"One more {item['name']}",
                          on_click=_add_one, args=(item["id"], item["name"]), disabled=not can_add)
            else:
                st.button("Add", key=f"add-{item['id']}", icon=":material/add_shopping_cart:", type="primary",
                          on_click=_add_one, args=(item["id"], item["name"]), disabled=not can_add,
                          help="Add one with no extras" if can_add else "Not available for this slot")
            if st.button("Details", key=f"details-{item['id']}", icon=":material/open_in_full:",
                         help=f"Ingredients, options and quantity for {item['name']}"):
                item_dialog(item["id"])


def _add_one(item_id: int, name: str) -> None:
    ui.cart_change(item_id, +1)
    ui.flash(f"Added {name} to your cart", "🛒")


@st.dialog("Dish details", width="large")
def item_dialog(item_id: int) -> None:
    with db.connection() as conn:
        item = next(row for row in inventory.list_menu(conn) if row["id"] == item_id)
        outlet = inventory.get_outlet(conn, item["outlet_id"])
    availability = ui.availability_map(st.session_state.slot_id)[item_id]
    in_cart = ui.cart_qty_for(item_id)
    room = max(availability.available - in_cart, 0) if availability.state == inventory.AVAILABLE else 0
    colour_a, colour_b = ui.item_colours(outlet)

    picture, info = st.columns([5, 6], gap="medium")
    with picture:
        st.html(ui.tile(item["emoji"], colour_a, colour_b, size="lg", chip_html=ui.availability_chip(availability),
                        label=item["name"]))
        st.html(ui.tags_html(item["tags"]))
    with info:
        st.html(
            f"<p class='eyebrow'>{esc(outlet['name'])} · {esc(item['category'])}</p>"
            f"<h2 style='margin:0;padding:0'>{esc(item['name'])}</h2>"
            f"<p class='money' style='font-size:1.35rem;margin:.2rem 0'>{money(item['price_paise'])}</p>"
            f"<p>{esc(item['description'])}</p>"
            f"<p class='muted'><b>Ingredients:</b> {esc(item['ingredients'])}</p>"
            f"<div class='meta'><span>⏱ Ready in about <b>{item['prep_minutes']} min</b></span>"
            f"<span>Pickup {esc(ui.short_slot(ui.orderable_slots()[st.session_state.slot_id]))}</span></div>"
        )
        chosen = []
        if item["options"]:
            st.html("<p class='eyebrow' style='margin-top:.6rem'>Customise</p>")
            for option in item["options"]:
                extra = f" (+{money(option['price_paise'])})" if option["price_paise"] else ""
                if st.checkbox(f"{option['label']}{extra}", key=f"opt-{item_id}-{option['label']}"):
                    chosen.append(option)
        if room == 0:
            message = (f"{item['name']} is unavailable for this slot ({availability.restriction})."
                       if availability.state == inventory.RESTRICTED else
                       "You already have all remaining units in your cart." if in_cart else
                       "Sold out for this slot. Try another pickup slot.")
            st.warning(message, icon=":material/info:")
            return
        qty = st.number_input("Quantity", min_value=1, max_value=min(room, 20), value=1, step=1,
                              key=f"qty-{item_id}", help=f"{room} more can be reserved for this slot")
        unit = item["price_paise"] + sum(option["price_paise"] for option in chosen)
        if st.button(f"Add to cart · {money(unit * qty)}", type="primary", icon=":material/add_shopping_cart:",
                     width="stretch", key=f"dialog-add-{item_id}"):
            ui.cart_add(item_id, int(qty), [option["label"] for option in chosen])
            ui.flash(f"Added {qty} × {item['name']} to your cart", "🛒")
            st.rerun()


# --- Cart, payment and confirmation ---------------------------------------------------------------

def cart_page() -> None:
    checkout = st.session_state.checkout
    stage = checkout["stage"] if checkout else "cart"
    profile_bar({"cart": "Your cart", "payment": "Payment", "done": "Order confirmed"}[stage], "Checkout")
    st.html(ui.steps_html(stage))
    if stage == "payment":
        payment_view(checkout["id"])
    elif stage == "done":
        confirmation_view(checkout["id"])
    else:
        cart_view()


def cart_view() -> None:
    if not ui.cart():
        ui.empty_state("🛍️", "Your cart is empty", "Browse the five campus outlets and add something tasty.")
        st.page_link(ui.PAGES["outlets"], label="Browse outlets", icon=":material/storefront:")
        return

    with db.connection() as conn:
        try:
            quote = pricing.quote(conn, ui.cart())
        except BusinessError as exc:  # an item or option no longer exists
            st.error(exc.message)
            if st.button("Empty cart"):
                st.session_state.cart = []
                st.rerun()
            return
        outlets = {outlet["id"]: outlet for outlet in inventory.list_outlets(conn)}

    items_col, summary_col = st.columns([3, 2], gap="large")
    with summary_col.container(key="panel-summary"):
        st.html("<h3 style='margin-top:0'>Order summary</h3>")
        slot_id = ui.slot_picker("pick-slot-cart")
        stock = ui.availability_map(slot_id)
        st.html(ui.bill_html(quote.subtotal, quote.tax, quote.fee, quote.total, len(quote.outlets)))
        st.caption(f"{len(quote.outlets)} outlet order{'s' if len(quote.outlets) > 1 else ''} · each outlet confirms "
                   "its own. Your whole cart is reserved together: if one dish can't be made, nothing is reserved.")
        if not (st.session_state.customer_name or "").strip():
            st.warning("Add your name (top right) so the counter can find your order.", icon=":material/badge:")
        if st.button(f"Place order · {money(quote.total)}", type="primary", icon=":material/lock:", width="stretch",
                     key="place-order", disabled=not (st.session_state.customer_name or "").strip()):
            place_order(slot_id)

    with items_col:
        for outlet_quote in quote.outlets:
            outlet = outlets[outlet_quote.outlet_id]
            with st.container(key=f"card-cart-{outlet['id']}"):
                st.html(f"<div class='price-row'><h3>{outlet['emoji']} {esc(outlet['name'])}</h3>"
                        f"<span class='muted'>ready in ~{outlet_quote.prep_minutes} min</span></div>")
                for line in outlet_quote.lines:
                    cart_line(line, outlet, stock[line.item_id])
                st.html(f"<div class='price-row'><span class='muted'>Outlet subtotal</span>"
                        f"<span class='money'>{money(outlet_quote.subtotal)}</span></div>")
        st.page_link(ui.PAGES["outlets"], label="Add more dishes", icon=":material/add:")


def cart_line(line: pricing.QuoteLine, outlet: dict, availability: inventory.ItemAvailability) -> None:
    total_for_item = ui.cart_qty_for(line.item_id)
    colour_a, colour_b = ui.item_colours(outlet)
    picture, text, controls = st.columns([1, 4, 3], vertical_alignment="center", gap="small")
    picture.html(ui.tile(line.emoji, colour_a, colour_b, size="sm", label=line.name))
    options = f"<span class='muted'>{esc(line.options_text)}</span><br>" if line.options else ""
    warning = ""
    if availability.state == inventory.RESTRICTED:
        warning = ui.chip(f"Unavailable for this slot ({availability.restriction})", "solid-bad")
    elif total_for_item > availability.available:
        warning = ui.chip(f"Only {availability.available} left for this slot", "solid-bad")
    text.html(f"<b>{esc(line.name)}</b><br>{options}<span class='muted'>{money(line.unit_price)} each</span>"
              f"<div>{warning}</div>")
    key = f"{line.item_id}-{'-'.join(line.options) or 'plain'}"
    with controls.container(horizontal=True, vertical_alignment="center", horizontal_alignment="right", gap="small"):
        st.button(":material/remove:", key=f"cart-less-{key}", help=f"One less {line.name}",
                  on_click=ui.cart_change, args=(line.item_id, -1, list(line.options)))
        st.html(f"<span class='money' aria-label='Quantity'>{line.qty}</span>", width="content")
        st.button(":material/add:", key=f"cart-more-{key}", help=f"One more {line.name}",
                  on_click=ui.cart_change, args=(line.item_id, +1, list(line.options)))
        st.button(":material/delete:", key=f"cart-remove-{key}", help=f"Remove {line.name}", type="tertiary",
                  on_click=_remove_line, args=(line.item_id, list(line.options), line.name))
        st.html(f"<span class='money'>{money(line.line_total)}</span>", width="content")


def _remove_line(item_id: int, options, name: str) -> None:
    ui.cart_remove(item_id, options)
    ui.flash(f"Removed {name}", "🗑️")


def place_order(slot_id: int) -> None:
    with st.spinner("Reserving your dishes…"):
        try:
            checkout = orders.submit_order(st.session_state.customer_name, slot_id, ui.cart(),
                                           customer_phone=st.session_state.customer_phone)
        except BusinessError as exc:
            st.error(exc.message, icon=":material/error:")
            return
    st.session_state.cart = []
    st.session_state.checkout = {"id": checkout.checkout_id, "stage": "payment"}
    ui.flash(f"Reserved! {len(checkout.order_ids)} order(s) placed. Choose how to pay.", "🎉")
    st.rerun()


def payment_view(checkout_id: str) -> None:
    placed = orders.list_orders(checkout_id=checkout_id)
    total = sum(order["total_paise"] for order in placed if order["status"] not in (Status.REJECTED, Status.CANCELLED))
    st.html("<div class='demo-note'>🧪 <b>Demo payment.</b> No money moves and no payment gateway is contacted.</div>")
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.html(f"<h3>Amount to pay <span class='money'>{money(total)}</span></h3>")
        with st.container(key="pay-method"):
            method = st.radio("Payment method", [orders.CASH, orders.UPI], key="w-pay-method",
                              captions=["Pay at the counter when you pick up your food.",
                                        "Pay now from any UPI app. Fastest pickup."],
                              label_visibility="collapsed")
        if method == orders.UPI:
            qr, form = st.columns([2, 3], gap="medium", vertical_alignment="center")
            qr.html(ui.demo_qr(checkout_id))
            with form:
                st.html("<p class='muted' style='margin:0'>Pay to <b>campusbites@demoupi</b></p>")
                upi_id = st.text_input("Your UPI ID", placeholder="name@bank", key="w-upi-id")
                valid = "@" in upi_id and len(upi_id.split("@")[0]) > 1 and len(upi_id.split("@")[1]) > 1
                if upi_id and not valid:
                    st.caption(":red[Enter a UPI ID like name@bank.]")
                if st.button(f"Pay {money(total)}", type="primary", icon=":material/qr_code_2:", width="stretch",
                             disabled=not valid, key="pay-upi"):
                    record_payment(checkout_id, orders.UPI, "Waiting for UPI approval… (demo)")
        else:
            if st.button("Confirm order · pay at pickup", type="primary", icon=":material/payments:",
                         width="stretch", key="pay-cash"):
                record_payment(checkout_id, orders.CASH, "Confirming your order…")
    with right.container(key="panel-paysummary"):
        st.html("<h3 style='margin-top:0'>Your orders</h3>")
        for order in placed:
            st.html(f"<div class='price-row'><span>{order['outlet_emoji']} <b>#{order['id']}</b> {esc(order['outlet'])}"
                    f"</span><span class='money'>{money(order['total_paise'])}</span></div>"
                    f"<p class='muted' style='margin:.1rem 0 .6rem'>"
                    f"{esc(', '.join(f'{i['qty']} × {i['name']}' for i in order['items']))}</p>")
        st.caption(f"Pickup {placed[0]['slot_label']}" if placed else "")


def record_payment(checkout_id: str, method: str, waiting: str) -> None:
    with st.spinner(waiting):
        time.sleep(0.8 if method == orders.UPI else 0.3)  # the demo gateway "thinks"
        try:
            orders.pay(checkout_id, method, st.session_state.customer_name)
        except BusinessError as exc:
            st.error(exc.message)
            return
    st.session_state.checkout = {"id": checkout_id, "stage": "done"}
    ui.flash("Payment recorded" if method == orders.UPI else "Order confirmed — pay at pickup", "✅")
    st.rerun()


def confirmation_view(checkout_id: str) -> None:
    name = (st.session_state.customer_name or "").split()[0] if st.session_state.customer_name else ""
    st.html(f"<div class='success'><div class='tick' aria-hidden='true'>✓</div>"
            f"<h1>Thanks{', ' + esc(name) if name else ''}! Your order is in.</h1>"
            "<p class='muted'>Each outlet will accept it shortly. This page updates live.</p></div>")
    live_checkout(checkout_id)
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.page_link(ui.PAGES["orders"], label="Track in My Orders", icon=":material/receipt_long:")
        if st.button("Order something else", icon=":material/restaurant:", key="new-order"):
            st.session_state.checkout = None
            st.switch_page(ui.PAGES["outlets"])


@st.fragment(run_every=3)
def live_checkout(checkout_id: str) -> None:
    for order in orders.list_orders(checkout_id=checkout_id):
        order_card(order, context="confirm")


# --- My Orders -------------------------------------------------------------------------------------

def orders_page() -> None:
    profile_bar("My Orders", "Track and reorder")
    name = (st.session_state.customer_name or "").strip()
    if not name:
        ui.empty_state("🙋", "Tell us who you are", "Add your name (top right) to see your orders.")
        return
    live_orders(name)


@st.fragment(run_every=3)
def live_orders(name: str) -> None:
    mine = orders.list_orders(customer_name=name)
    active = [order for order in mine if order["is_active"]]
    past = [order for order in mine if not order["is_active"]]
    st.caption(f"Live · updated {time.strftime('%H:%M:%S')}")
    active_tab, past_tab = st.tabs([f"Active ({len(active)})", f"Previous ({len(past)})"])
    with active_tab:
        if not active:
            ui.empty_state("🍽️", "No active orders", "When you place an order, its progress shows up here live.")
            st.page_link(ui.PAGES["outlets"], label="Browse outlets", icon=":material/storefront:")
        for order in active:
            order_card(order)
    with past_tab:
        if not past:
            ui.empty_state("🧾", "No previous orders yet", "Delivered, completed and cancelled orders appear here.")
        for order in past:
            order_card(order)


def order_card(order: dict, context: str = "orders") -> None:
    order_id = order["id"]
    with st.container(key=f"card-order-{context}-{order_id}"):
        head, amount = st.columns([3, 2], vertical_alignment="top")
        with head:
            st.html(
                f"<div style='display:flex;gap:.8rem;align-items:center'>"
                + ui.tile(order["outlet_emoji"], order["colour_a"], order["colour_b"], size="sm", label=order["outlet"])
                + f"<div><h3>Order #{order_id} · {esc(order['outlet'])}</h3>"
                f"<div class='meta'><span>Placed {ui.when(order['created_at'])}</span>"
                f"<span>Pickup {esc(order['slot_label'])}</span></div></div></div>"
            )
        with amount:
            with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
                ui.status_badge(order["status"])
                st.html(f"<span class='money' style='font-size:1.15rem'>{money(order['total_paise'])}</span>", width="content")
            st.html(f"<div style='text-align:right'>{ui.payment_chip(order)}</div>")
        st.html(ui.timeline_html(order))
        st.html(ui.lines_table(order["items"], show_unit=False))
        if order["status"] in (Status.REJECTED, Status.CANCELLED) and order["reason"]:
            st.html(f"<p class='muted' style='margin:.4rem 0 0'><b>{esc(order['status'])}:</b> {esc(order['reason'])}</p>")
        elif order["status"] in (Status.ACCEPTED, Status.PREPARING):
            st.html(f"<p class='muted' style='margin:.4rem 0 0'>⏱ The outlet expects it ready in about "
                    f"<b>{order['estimated_minutes']} min</b>.</p>")
        elif order["status"] == Status.PLACED:
            st.html(f"<p class='muted' style='margin:.4rem 0 0'>Waiting for {esc(order['outlet'])} to accept · usually "
                    f"about {order['estimated_minutes']} min to prepare.</p>")
        elif order["status"] == Status.READY:
            st.html("<p style='margin:.4rem 0 0'><b>🔔 Ready at the counter.</b> Show your order number to collect.</p>")
        if context == "orders":
            order_actions(order)


def order_actions(order: dict) -> None:
    order_id = order["id"]
    with st.container(horizontal=True, gap="small"):
        if order["payment_status"] == "Pending" and order["status"] not in (Status.REJECTED, Status.CANCELLED):
            if st.button("Pay now", key=f"pay-{order_id}", icon=":material/payments:", type="primary"):
                st.session_state.checkout = {"id": order["checkout_id"], "stage": "payment"}
                st.switch_page(ui.PAGES["cart"])
        if order["status"] == Status.ACCEPTED:
            if st.session_state.confirm_cancel == order_id:
                st.html("<span class='chip solid-warn'>Cancel this order?</span>", width="content")
                if st.button("Yes, cancel", key=f"cancel-yes-{order_id}", icon=":material/cancel:"):
                    st.session_state.confirm_cancel = None
                    try:
                        orders.transition(order_id, "cancel", orders.CUSTOMER, actor_name=st.session_state.customer_name)
                        ui.flash(f"Order #{order_id} cancelled. Its items are available again.", "↩️")
                    except BusinessError as exc:
                        ui.flash(exc.message, "⚠️")
                    st.rerun()
                if st.button("Keep order", key=f"cancel-no-{order_id}"):
                    st.session_state.confirm_cancel = None
                    st.rerun()
            elif st.button("Cancel order", key=f"cancel-{order_id}", icon=":material/close:",
                           help="Possible until the outlet starts preparing"):
                st.session_state.confirm_cancel = order_id
                st.rerun()
        elif order["status"] in (Status.PREPARING, Status.READY):
            st.caption("Preparation has started, so this order can no longer be cancelled.")
        if order["customer_name"] != "Pre-existing (seed)":
            if st.button("Reorder", key=f"reorder-{order_id}", icon=":material/replay:"):
                lines = orders.reorder_lines(order_id)
                for line in lines:
                    ui.cart_add(line["item_id"], line["qty"], line["options"])
                ui.flash(f"Added {sum(line['qty'] for line in lines)} item(s) from order #{order_id} to your cart", "🛒")
                st.rerun()
