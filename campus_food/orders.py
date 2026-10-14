"""Checkout, payment and the order lifecycle (BRD sections 4 and 8).

A cart can hold items from several outlets. Checkout creates one order per
outlet - each outlet accepts or rejects its own order - but all of them are
validated and created in ONE transaction, so the cart is still all-or-nothing.

Every status change goes through `transition`, driven by the ACTIONS table.
Anything not in the table is refused.
"""

import secrets
from dataclasses import dataclass
from datetime import date, datetime

from . import db, inventory, pricing
from .errors import AvailabilityError, InvalidTransition, NotFound, ValidationError
from .status import ACTIVE, Status

CUSTOMER = "customer"
STAFF = "staff"

CASH = "Cash on Delivery"
UPI = "UPI"


@dataclass(frozen=True)
class Action:
    from_status: str
    to_status: str
    role: str
    label: str


# LC-02 to LC-06b. Release of stock is not an explicit step: Rejected and
# Cancelled are outside status.COUNTED, so the lines stop counting (INV-06).
ACTIONS = {
    "accept": Action(Status.PLACED, Status.ACCEPTED, STAFF, "accept"),
    "reject": Action(Status.PLACED, Status.REJECTED, STAFF, "reject"),
    "cancel": Action(Status.ACCEPTED, Status.CANCELLED, CUSTOMER, "cancel"),
    "start_preparing": Action(Status.ACCEPTED, Status.PREPARING, STAFF, "start preparing"),
    "mark_ready": Action(Status.PREPARING, Status.READY, STAFF, "mark ready"),
    "deliver": Action(Status.READY, Status.DELIVERED, STAFF, "mark delivered"),
    "complete": Action(Status.DELIVERED, Status.COMPLETED, STAFF, "complete"),
}
# The challenge PDF's names for two of the actions.
ACTIONS["confirm"] = ACTIONS["accept"]
ACTIONS["collect"] = ACTIONS["deliver"]

MIN_PREP_MINUTES, MAX_PREP_MINUTES = 1, 240


@dataclass(frozen=True)
class Checkout:
    checkout_id: str
    order_ids: tuple[int, ...]


def submit_order(customer_name: str, slot_id: int, cart, customer_phone: str | None = None,
                 db_path=None) -> Checkout:
    """Validate the complete cart and reserve every line atomically, or reserve
    nothing (FR-01 to FR-07, BC-1 to BC-4, BC-12). Creates one Placed order per
    outlet, priced by `pricing.quote`."""
    name = (customer_name or "").strip()
    if not name:
        raise ValidationError("Enter your name before placing an order.")
    lines = pricing.normalise_cart(cart)
    if not lines:
        raise ValidationError("Add at least one item with a quantity of 1 or more.")
    phone = (customer_phone or "").strip() or None

    with db.connection(db_path) as conn:
        slot = inventory.get_slot(conn, slot_id)
        quote = pricing.quote(conn, lines)  # also rejects unknown items and options

        with db.write_transaction(conn):
            # Rechecked inside the write lock: what the menu showed earlier is advisory (INV-09).
            totals: dict[int, int] = {}
            for line in lines:
                totals[line["item_id"]] = totals.get(line["item_id"], 0) + line["qty"]
            failures = inventory.check_lines(conn, slot_id, totals)
            if failures:
                raise AvailabilityError(failures, inventory.slot_label(slot))

            checkout_id = secrets.token_hex(4).upper()
            timestamp = db.now()
            order_ids = []
            for outlet_quote in quote.outlets:
                order_id = conn.execute(
                    "INSERT INTO orders (checkout_id, customer_name, customer_phone, outlet_id, slot_id, status, "
                    "reason, prep_minutes, subtotal_paise, tax_paise, fee_paise, total_paise, payment_method, "
                    "payment_status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, NULL, 'Pending', ?, ?)",
                    (checkout_id, name, phone, outlet_quote.outlet_id, slot_id, Status.PLACED,
                     outlet_quote.subtotal, outlet_quote.tax, outlet_quote.fee, outlet_quote.total,
                     timestamp, timestamp),
                ).lastrowid
                conn.executemany(
                    "INSERT INTO order_item (order_id, item_id, qty, unit_price_paise, options) VALUES (?, ?, ?, ?, ?)",
                    [(order_id, line.item_id, line.qty, line.unit_price, line.options_text)
                     for line in outlet_quote.lines],
                )
                _log(conn, order_id, Status.PLACED, timestamp)
                order_ids.append(order_id)
    return Checkout(checkout_id, tuple(order_ids))


def pay(checkout_id: str, method: str, customer_name: str, db_path=None) -> list[dict]:
    """Record the demo payment for every open order in a checkout. No money moves:
    UPI is marked Paid, Cash on Delivery is collected at pickup."""
    if method not in (CASH, UPI):
        raise ValidationError(f"Choose a payment method: {CASH} or {UPI}.")
    with db.connection(db_path) as conn:
        with db.write_transaction(conn):
            rows = conn.execute(
                "SELECT id, customer_name, status, payment_status FROM orders WHERE checkout_id = ?", (checkout_id,)
            ).fetchall()
            if not rows:
                raise NotFound(f"No checkout {checkout_id} found.")
            if rows[0]["customer_name"].strip().lower() != (customer_name or "").strip().lower():
                raise InvalidTransition("This checkout belongs to another customer.")
            pending = [row["id"] for row in rows
                       if row["payment_status"] == "Pending" and row["status"] not in (Status.REJECTED, Status.CANCELLED)]
            if not pending:
                raise InvalidTransition("Payment for this order has already been recorded.")
            conn.executemany(
                "UPDATE orders SET payment_method = ?, payment_status = ?, updated_at = ? WHERE id = ?",
                [(method, "Paid" if method == UPI else "Pay at pickup", db.now(), order_id) for order_id in pending],
            )
    return list_orders(checkout_id=checkout_id, db_path=db_path)


def transition(order_id: int, action: str, actor_role: str, actor_name: str | None = None,
               reason: str | None = None, prep_minutes: int | None = None, db_path=None) -> dict:
    """Apply one lifecycle action, or refuse it with a specific message
    (FR-10 to FR-15, LC-01 to LC-07, ERR-07 to ERR-11, ERR-13)."""
    act = ACTIONS.get(action)
    if act is None:
        raise ValidationError(f"Unknown action '{action}'.")
    if actor_role != act.role:
        who = "the customer" if act.role == CUSTOMER else "the outlet"
        raise InvalidTransition(f"Only {who} can {act.label} an order.")
    reason = (reason or "").strip() or None
    if act.to_status == Status.REJECTED and not reason:
        raise ValidationError("Give a reason when rejecting an order.")
    if prep_minutes is not None:
        _check_prep_minutes(prep_minutes)

    with db.connection(db_path) as conn:
        with db.write_transaction(conn):
            order = conn.execute(
                "SELECT id, customer_name, status, payment_status FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if order is None:
                raise NotFound(f"No order #{order_id} found.")
            if act.role == CUSTOMER and order["customer_name"].strip().lower() != (actor_name or "").strip().lower():
                raise InvalidTransition(f"Order #{order_id} belongs to another customer.")
            if order["status"] != act.from_status:
                raise InvalidTransition(_refusal(order_id, act, order["status"]))

            payment_status = order["payment_status"]
            if act.to_status in (Status.REJECTED, Status.CANCELLED) and payment_status == "Paid":
                payment_status = "Refunded"  # demo refund of a UPI payment
            if act.to_status == Status.COMPLETED and payment_status == "Pay at pickup":
                payment_status = "Paid"  # cash collected at the counter
            if act.to_status == Status.ACCEPTED and prep_minutes is None:
                prep_minutes = _estimate(conn, order_id)

            timestamp = db.now()
            # Conditional update: only succeeds if nobody changed the status meanwhile (A-14).
            updated = conn.execute(
                "UPDATE orders SET status = ?, reason = COALESCE(?, reason), "
                "prep_minutes = COALESCE(?, prep_minutes), payment_status = ?, updated_at = ? "
                "WHERE id = ? AND status = ?",
                (act.to_status, reason, prep_minutes, payment_status, timestamp, order_id, act.from_status),
            ).rowcount
            if updated != 1:
                raise InvalidTransition(f"Order #{order_id} was changed by someone else. Refresh and try again.")
            _log(conn, order_id, act.to_status, timestamp)
    return get_order(order_id, db_path=db_path)


def set_prep_minutes(order_id: int, minutes: int, db_path=None) -> dict:
    """Outlet updates the expected preparation time of an accepted or preparing order."""
    _check_prep_minutes(minutes)
    with db.connection(db_path) as conn:
        with db.write_transaction(conn):
            order = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
            if order is None:
                raise NotFound(f"No order #{order_id} found.")
            if order["status"] not in (Status.ACCEPTED, Status.PREPARING):
                raise InvalidTransition(
                    f"Order #{order_id} is {order['status']}. Preparation time can only change while it is "
                    f"{Status.ACCEPTED} or {Status.PREPARING}."
                )
            conn.execute("UPDATE orders SET prep_minutes = ?, updated_at = ? WHERE id = ?",
                         (minutes, db.now(), order_id))
    return get_order(order_id, db_path=db_path)


def _check_prep_minutes(minutes) -> None:
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not MIN_PREP_MINUTES <= minutes <= MAX_PREP_MINUTES:
        raise ValidationError(
            f"Preparation time must be a whole number of minutes from {MIN_PREP_MINUTES} to {MAX_PREP_MINUTES}."
        )


def _estimate(conn, order_id: int) -> int:
    return conn.execute(
        "SELECT MAX(m.prep_minutes) FROM order_item oi JOIN menu_item m ON m.id = oi.item_id WHERE oi.order_id = ?",
        (order_id,),
    ).fetchone()[0]


def _log(conn, order_id: int, status: str, at: str) -> None:
    conn.execute("INSERT INTO order_event (order_id, status, at) VALUES (?, ?, ?)", (order_id, status, at))


def _refusal(order_id: int, act: Action, current: str) -> str:
    if current in (Status.DELIVERED, Status.COMPLETED) and act.to_status == Status.DELIVERED:
        return f"Order #{order_id} has already been delivered."
    if current == Status.COMPLETED:
        return f"Order #{order_id} is complete, so it cannot be changed."
    if current in (Status.REJECTED, Status.CANCELLED):
        return f"Order #{order_id} is closed ({current}), so it cannot be changed."
    if act.to_status == Status.CANCELLED and current in (Status.PREPARING, Status.READY, Status.DELIVERED):
        return f"Order #{order_id} is {current}: preparation has started, so it can no longer be cancelled."
    if act.to_status == Status.CANCELLED and current == Status.PLACED:
        return (f"Order #{order_id} is still waiting for the outlet to accept it. "
                "Only accepted orders can be cancelled.")
    return f"Order #{order_id} is {current}. To {act.label} it, it must be {act.from_status}."


def list_orders(slot_id: int | None = None, statuses=None, customer_name: str | None = None,
                outlet_id: int | None = None, order_id: int | None = None, checkout_id: str | None = None,
                db_path=None) -> list[dict]:
    """Orders with outlet, lines, prices and status history, newest first. Filters are optional (FR-08, FR-09)."""
    where, params = [], []
    for column, value in (("o.id", order_id), ("o.slot_id", slot_id), ("o.outlet_id", outlet_id),
                          ("o.checkout_id", checkout_id)):
        if value is not None:
            where.append(f"{column} = ?")
            params.append(value)
    if statuses:
        where.append(f"o.status IN ({', '.join('?' for _ in statuses)})")
        params.extend(statuses)
    if customer_name is not None:
        where.append("lower(trim(o.customer_name)) = lower(trim(?))")
        params.append(customer_name)
    sql = (
        "SELECT o.*, s.slot_date, s.start_time, s.end_time, "
        "ou.name AS outlet, ou.emoji AS outlet_emoji, ou.colour_a, ou.colour_b "
        "FROM orders o JOIN pickup_slot s ON s.id = o.slot_id JOIN outlet ou ON ou.id = o.outlet_id"
        + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY o.id DESC"
    )
    with db.connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        ids = [row["id"] for row in rows]
        marks = ", ".join("?" for _ in ids)
        lines = conn.execute(
            "SELECT oi.order_id, oi.item_id, m.name, m.emoji, m.prep_minutes, oi.qty, oi.unit_price_paise, oi.options "
            f"FROM order_item oi JOIN menu_item m ON m.id = oi.item_id WHERE oi.order_id IN ({marks}) ORDER BY oi.id",
            ids,
        ).fetchall() if ids else []
        events = conn.execute(
            f"SELECT order_id, status, at FROM order_event WHERE order_id IN ({marks}) ORDER BY id", ids,
        ).fetchall() if ids else []

    items_by_order: dict[int, list[dict]] = {}
    for line in lines:
        items_by_order.setdefault(line["order_id"], []).append({
            "item_id": line["item_id"], "name": line["name"], "emoji": line["emoji"], "qty": line["qty"],
            "unit_price_paise": line["unit_price_paise"], "line_total_paise": line["unit_price_paise"] * line["qty"],
            "options": [option for option in line["options"].split(", ") if option],
            "prep_minutes": line["prep_minutes"],
        })
    events_by_order: dict[int, dict[str, str]] = {}
    for event in events:
        events_by_order.setdefault(event["order_id"], {})[event["status"]] = event["at"]

    result = []
    for row in rows:
        items = items_by_order.get(row["id"], [])
        result.append({
            **dict(row),
            "slot_label": inventory.slot_label(row),
            "items": items,
            "events": events_by_order.get(row["id"], {}),
            "estimated_minutes": row["prep_minutes"] or max((item["prep_minutes"] for item in items), default=0),
            "is_active": row["status"] in ACTIVE,
        })
    return result


def get_order(order_id: int, db_path=None) -> dict:
    found = list_orders(order_id=order_id, db_path=db_path)
    if not found:
        raise NotFound(f"No order #{order_id} found.")
    return found[0]


def reorder_lines(order_id: int, db_path=None) -> list[dict]:
    """Cart lines that repeat a previous order: same items, quantities and options."""
    return [{"item_id": item["item_id"], "qty": item["qty"], "options": list(item["options"])}
            for item in get_order(order_id, db_path=db_path)["items"]]


def vendor_metrics(outlet_id: int | None = None, day: date | None = None, db_path=None) -> dict:
    """Summary for the vendor dashboard. Revenue counts today's orders that were
    not rejected or cancelled; 'completed' counts orders handed over (Delivered or Completed)."""
    day_text = (day or date.today()).isoformat()
    where, params = ["substr(created_at, 1, 10) = ?"], [day_text]
    if outlet_id is not None:
        where.append("outlet_id = ?")
        params.append(outlet_id)
    clause = " AND ".join(where)
    with db.connection(db_path) as conn:
        today = conn.execute(f"SELECT status, total_paise FROM orders WHERE {clause}", params).fetchall()
        pending = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = ?" + (" AND outlet_id = ?" if outlet_id is not None else ""),
            (Status.PLACED, outlet_id) if outlet_id is not None else (Status.PLACED,),
        ).fetchone()[0]
    return {
        "revenue_paise": sum(row["total_paise"] for row in today
                             if row["status"] not in (Status.REJECTED, Status.CANCELLED)),
        "orders_today": len(today),
        "pending": pending,
        "completed_today": sum(1 for row in today if row["status"] in (Status.DELIVERED, Status.COMPLETED)),
    }


def minutes_since(timestamp: str) -> int:
    return max(int((datetime.now() - datetime.fromisoformat(timestamp)).total_seconds() // 60), 0)
