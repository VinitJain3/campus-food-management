"""Shared UI pieces: session state, cart, food tiles, badges, timeline and messages.

Nothing here decides a business rule. Prices come from campus_food.pricing,
availability from campus_food.inventory, status changes from campus_food.orders.
"""

import base64
import hashlib
import html
from datetime import date, datetime

import streamlit as st

from campus_food import db, inventory, pricing, seed_data
from campus_food.status import TIMELINE, Status

esc = html.escape
money = pricing.rupees

ALL_OUTLETS = 0  # vendor outlet filter value meaning "every outlet" (outlet ids start at 1)

# Pages registered by app.py on every run, so screens can link to each other.
PAGES: dict = {}

STATUS_STYLE = {
    Status.PLACED: ("orange", ":material/schedule:"),
    Status.ACCEPTED: ("blue", ":material/thumb_up:"),
    Status.PREPARING: ("violet", ":material/skillet:"),
    Status.READY: ("green", ":material/notifications_active:"),
    Status.DELIVERED: ("green", ":material/takeout_dining:"),
    Status.COMPLETED: ("gray", ":material/task_alt:"),
    Status.REJECTED: ("red", ":material/block:"),
    Status.CANCELLED: ("gray", ":material/cancel:"),
}
PAYMENT_STYLE = {"Paid": "solid-ok", "Pay at pickup": "solid-warn", "Pending": "solid-bad", "Refunded": "solid-teal"}
DIET_CLASS = {"Veg": "veg", "Vegan": "vegan", "Contains egg": "egg"}


# --- Session state -----------------------------------------------------------------------------

def init_state() -> None:
    defaults = {
        "mode": "customer",
        "cart": [],
        "customer_name": seed_data.DEMO_CUSTOMER["name"],
        "customer_phone": seed_data.DEMO_CUSTOMER["phone"],
        "slot_id": None,
        "checkout": None,         # {"id": checkout id, "stage": "payment" | "done"}
        "vendor_outlet": ALL_OUTLETS,
        "confirm_cancel": None,
        "flash": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if st.session_state.slot_id is None:
        slots = orderable_slots()
        preferred = [sid for sid, slot in slots.items() if (slot["slot_date"], slot["start_time"]) == ("2026-08-04", "13:00")]
        st.session_state.slot_id = preferred[0] if preferred else next(iter(slots))


def _copy(widget_key: str, state_key: str) -> None:
    st.session_state[state_key] = st.session_state[widget_key]


def bound(widget, label: str, state_key: str, widget_key: str, **kwargs):
    """A widget whose value lives in a persistent session key. Streamlit forgets a
    widget's own key when a page that does not draw it runs, so the value is
    copied to `state_key` and restored into the widget on every run."""
    st.session_state[widget_key] = st.session_state[state_key]
    return widget(label, key=widget_key, on_change=_copy, args=(widget_key, state_key), **kwargs)


def flash(message: str, icon: str = "✅") -> None:
    st.session_state.flash.append((message, icon))


def show_flash() -> None:
    for message, icon in st.session_state.flash:
        st.toast(message, icon=icon)
    st.session_state.flash = []


# --- Cart (local session state; priced and validated by the core) ------------------------------

def cart() -> list[dict]:
    return st.session_state.cart


def cart_count() -> int:
    return sum(line["qty"] for line in cart())


def cart_qty_for(item_id: int) -> int:
    return sum(line["qty"] for line in cart() if line["item_id"] == item_id)


def cart_add(item_id: int, qty: int = 1, options=()) -> None:
    options = sorted(options)
    for line in cart():
        if line["item_id"] == item_id and line["options"] == options:
            line["qty"] += qty
            return
    cart().append({"item_id": item_id, "qty": qty, "options": options})


def cart_change(item_id: int, delta: int, options=None) -> None:
    """+1 / -1 on a line; with no options given, the plainest line of that item."""
    lines = [line for line in cart() if line["item_id"] == item_id and (options is None or line["options"] == sorted(options))]
    if not lines:
        if delta > 0:
            cart_add(item_id, delta)
        return
    line = min(lines, key=lambda l: len(l["options"])) if options is None else lines[0]
    line["qty"] += delta
    if line["qty"] <= 0:
        cart().remove(line)


def cart_remove(item_id: int, options) -> None:
    st.session_state.cart = [line for line in cart() if not (line["item_id"] == item_id and line["options"] == sorted(options))]


# --- Slots -------------------------------------------------------------------------------------

def orderable_slots() -> dict:
    with db.connection() as conn:
        return {row["id"]: dict(row) for row in inventory.list_slots(conn, orderable_only=True)}


def short_slot(slot) -> str:
    day = date.fromisoformat(slot["slot_date"])
    return f"{day:%a} {day.day} {day:%b} · {slot['start_time']}–{slot['end_time']}"


def slot_picker(widget_key: str, label: str = "Pickup slot") -> int:
    slots = orderable_slots()
    return bound(st.selectbox, label, "slot_id", widget_key, options=list(slots),
                 format_func=lambda sid: short_slot(slots[sid]),
                 help="Stock is limited per item for each 30-minute pickup slot.")


def availability_map(slot_id: int) -> dict[int, inventory.ItemAvailability]:
    with db.connection() as conn:
        return {item.item_id: item for item in inventory.get_availability(conn, slot_id)}


# --- HTML pieces -------------------------------------------------------------------------------

def tint(hex_colour: str, amount: float) -> str:
    """Mix a #RRGGBB colour with white (amount 0..1)."""
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    mix = lambda c: round(c + (255 - c) * amount)  # noqa: E731
    return f"#{mix(r):02X}{mix(g):02X}{mix(b):02X}"


def tile(emoji: str, colour_a: str, colour_b: str, size: str = "", chip_html: str = "", dim: bool = False,
         label: str = "") -> str:
    classes = " ".join(c for c in ("tile", size, "dim" if dim else "") if c)
    if len(emoji) == 1:
        emoji += "️"  # force the colour emoji (e.g. ☕ otherwise draws as a text glyph)
    return (f'<div class="{classes}" style="--a:{colour_a};--b:{colour_b}" role="img" aria-label="{esc(label)}">'
            f'<span class="emoji" aria-hidden="true">{emoji}</span>{chip_html}</div>')


def item_colours(outlet: dict) -> tuple[str, str]:
    return tint(outlet["colour_a"], 0.25), tint(outlet["colour_b"], 0.35)


def chip(text: str, kind: str = "", extra: str = "") -> str:
    return f'<span class="chip {kind} {extra}">{esc(text)}</span>'


def availability_chip(item: inventory.ItemAvailability, right: bool = False) -> str:
    side = "right" if right else ""
    if item.state == inventory.RESTRICTED:
        return chip("Unavailable", "bad", side)
    if item.state == inventory.SOLD_OUT:
        return chip("Sold out", "bad", side)
    if item.available <= inventory.LOW_STOCK:
        return chip(f"Only {item.available} left", "warn", side)
    return chip(f"{item.available} left", "ok", side)


def tags_html(tags) -> str:
    return '<div class="tags">' + "".join(
        f'<span class="tag {DIET_CLASS.get(tag, "")}">{esc(tag)}</span>' for tag in tags) + "</div>"


def lines_table(items, show_unit: bool = True) -> str:
    rows = "".join(
        f"<tr><td>{item['emoji']} {esc(item['name'])}"
        + (f"<span class='opt'>{esc(', '.join(item['options']))}</span>" if item["options"] else "")
        + f"</td><td class='n'>× {item['qty']}</td>"
        + (f"<td class='n'>{money(item['unit_price_paise'])}</td>" if show_unit else "")
        + f"<td class='n'>{money(item['line_total_paise'])}</td></tr>"
        for item in items
    )
    head = "<tr><th>Item</th><th class='n'>Qty</th>" + ("<th class='n'>Price</th>" if show_unit else "") + "<th class='n'>Total</th></tr>"
    return f"<table class='lines'>{head}{rows}</table>"


def bill_html(subtotal: int, tax: int, fee: int, total: int, outlet_count: int = 1) -> str:
    fee_label = "Pickup &amp; packaging fee" + (f" (₹{seed_data.PICKUP_FEE_RUPEES} × {outlet_count} outlets)" if outlet_count > 1 else "")
    return (f"<table class='bill'><tr><td>Subtotal</td><td>{money(subtotal)}</td></tr>"
            f"<tr><td>GST ({seed_data.TAX_RATE_PERCENT}%)</td><td>{money(tax)}</td></tr>"
            f"<tr><td>{fee_label}</td><td>{money(fee)}</td></tr>"
            f"<tr class='total'><td>Total</td><td>{money(total)}</td></tr></table>")


def clock(timestamp: str | None) -> str:
    return datetime.fromisoformat(timestamp).strftime("%H:%M") if timestamp else ""


def when(timestamp: str) -> str:
    moment = datetime.fromisoformat(timestamp)
    return f"{moment.day} {moment:%b %Y}, {moment:%H:%M}"


def timeline_html(order: dict) -> str:
    events, status = order["events"], order["status"]
    steps = []
    if status in (Status.REJECTED, Status.CANCELLED):
        for step in TIMELINE:
            if step in events:
                steps.append(("done", step, "✓", events[step]))
        steps.append(("stop", status, "✕", events.get(status)))
    else:
        reached = TIMELINE.index(status)
        for index, step in enumerate(TIMELINE):
            if index < reached or status == Status.COMPLETED:
                steps.append(("done", step, "✓", events.get(step)))
            elif index == reached:
                steps.append(("current", step, str(index + 1), events.get(step)))
            else:
                steps.append(("", step, str(index + 1), None))
    items = "".join(
        f'<li class="{cls}" aria-current="{"step" if cls == "current" else "false"}"><span class="dot">{mark}</span>'
        f'<span class="lbl">{esc(label)}</span><span class="t">{clock(at)}</span></li>'
        for cls, label, mark, at in steps
    )
    return f'<ol class="tl" aria-label="Order status: {esc(status)}">{items}</ol>'


def steps_html(stage: str) -> str:
    order = ["Cart", "Payment", "Confirmed"]
    current = {"cart": 0, "payment": 1, "done": 2}[stage]
    return '<ol class="steps" aria-label="Checkout progress">' + "".join(
        f'<li class="{"on" if i == current else ("done" if i < current else "")}">'
        f'<span>{"✓" if i < current else i + 1}</span>{name}</li>'
        for i, name in enumerate(order)) + "</ol>"


def empty_state(emoji: str, title: str, text: str) -> None:
    st.html(f'<div class="empty"><div class="big" aria-hidden="true">{emoji}</div><h3>{esc(title)}</h3><p>{esc(text)}</p></div>')


def status_badge(status: str) -> None:
    colour, icon = STATUS_STYLE[status]
    st.badge(status, icon=icon, color=colour)


def payment_chip(order: dict) -> str:
    method = order["payment_method"] or "Payment pending"
    state = order["payment_status"]
    label = method if state == "Pending" and not order["payment_method"] else f"{method} · {state}"
    return chip(label, PAYMENT_STYLE.get(state, ""))


def demo_qr(seed: str, size: int = 25) -> str:
    """A QR-looking pattern for the demo UPI screen. It encodes nothing and cannot be scanned."""
    bits = "".join(f"{byte:08b}" for byte in hashlib.sha256(seed.encode()).digest() * 3)
    cell, cells = 6, []
    finder = lambda r, c, r0, c0: (0 <= r - r0 < 7 and 0 <= c - c0 < 7) and (  # noqa: E731
        r - r0 in (0, 6) or c - c0 in (0, 6) or (2 <= r - r0 <= 4 and 2 <= c - c0 <= 4))
    near_finder = lambda r, c: (r < 8 and c < 8) or (r < 8 and c >= size - 8) or (r >= size - 8 and c < 8)  # noqa: E731
    for r in range(size):
        for c in range(size):
            on = finder(r, c, 0, 0) or finder(r, c, 0, size - 7) or finder(r, c, size - 7, 0)
            if not near_finder(r, c):
                on = bits[(r * size + c) % len(bits)] == "1"
            if on:
                cells.append(f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" height="{cell}"/>')
    side = size * cell
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}">'
           f'<g fill="#1C1917">{"".join(cells)}</g></svg>')
    # As an <img>: Streamlit's HTML sanitiser drops inline SVG shapes.
    data = base64.b64encode(svg.encode()).decode()
    return f'<img class="qr" src="data:image/svg+xml;base64,{data}" alt="Demo UPI QR code (not scannable)">'
