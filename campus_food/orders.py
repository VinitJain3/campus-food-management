"""Pre-order submission and the order lifecycle (BRD sections 4 and 8).

Every status change goes through `transition`, driven by the ACTIONS table.
Anything not in the table is refused.
"""

from dataclasses import dataclass

from . import db, inventory
from .errors import AvailabilityError, InvalidTransition, NotFound, ValidationError
from .status import Status

CUSTOMER = "customer"
STAFF = "staff"


@dataclass(frozen=True)
class Action:
    from_status: str
    to_status: str
    role: str
    label: str


# LC-02 to LC-06b. Release of stock is not an explicit step: Rejected and
# Cancelled are outside status.COUNTED, so the lines stop counting (INV-06).
ACTIONS = {
    "confirm": Action(Status.SUBMITTED, Status.CONFIRMED, STAFF, "confirm"),
    "reject": Action(Status.SUBMITTED, Status.REJECTED, STAFF, "reject"),
    "cancel": Action(Status.CONFIRMED, Status.CANCELLED, CUSTOMER, "cancel"),
    "start_preparing": Action(Status.CONFIRMED, Status.PREPARING, STAFF, "start preparing"),
    "mark_ready": Action(Status.PREPARING, Status.READY, STAFF, "mark ready for pickup"),
    "collect": Action(Status.READY, Status.COLLECTED, STAFF, "mark collected"),
}


def _normalise_cart(cart) -> dict[int, int]:
    """Accepts {item_id: qty} or [(item_id, qty), ...]. Repeated items are merged
    into one line (FR-04). Quantities must be whole numbers of at least 1."""
    pairs = cart.items() if isinstance(cart, dict) else cart
    lines: dict[int, int] = {}
    for item_id, qty in pairs:
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            raise ValidationError(f"Quantity must be a whole number of 1 or more (got {qty!r}).")
        lines[item_id] = lines.get(item_id, 0) + qty
    return lines


def submit_order(customer_name: str, slot_id: int, cart, db_path=None) -> int:
    """Validate the complete order and reserve every line atomically, or reserve
    nothing (FR-01 to FR-07, BC-1 to BC-4, BC-12). Returns the new order id."""
    name = (customer_name or "").strip()
    if not name:
        raise ValidationError("Enter your name before placing an order.")
    lines = _normalise_cart(cart)
    if not lines:
        raise ValidationError("Add at least one item with a quantity of 1 or more.")

    with db.connection(db_path) as conn:
        slot = inventory.get_slot(conn, slot_id)
        menu_ids = {row["id"] for row in inventory.list_menu(conn)}
        unknown = sorted(set(lines) - menu_ids)
        if unknown:
            raise ValidationError(f"Unknown menu item id(s): {unknown}.")

        with db.write_transaction(conn):
            # Rechecked inside the write lock: what the menu showed earlier is advisory (INV-09).
            failures = inventory.check_lines(conn, slot_id, lines)
            if failures:
                raise AvailabilityError(failures, inventory.slot_label(slot))
            timestamp = db.now()
            order_id = conn.execute(
                "INSERT INTO orders (customer_name, slot_id, status, reason, created_at, updated_at) "
                "VALUES (?, ?, ?, NULL, ?, ?)",
                (name, slot_id, Status.SUBMITTED, timestamp, timestamp),
            ).lastrowid
            conn.executemany(
                "INSERT INTO order_item (order_id, item_id, qty) VALUES (?, ?, ?)",
                [(order_id, item_id, qty) for item_id, qty in lines.items()],
            )
    return order_id


def transition(order_id: int, action: str, actor_role: str, actor_name: str | None = None,
               reason: str | None = None, db_path=None) -> dict:
    """Apply one lifecycle action, or refuse it with a specific message
    (FR-10 to FR-15, LC-01 to LC-07, ERR-07 to ERR-11, ERR-13)."""
    act = ACTIONS.get(action)
    if act is None:
        raise ValidationError(f"Unknown action '{action}'.")
    if actor_role != act.role:
        who = "the customer" if act.role == CUSTOMER else "outlet staff"
        raise InvalidTransition(f"Only {who} can {act.label} an order.")
    reason = (reason or "").strip() or None
    if action == "reject" and not reason:
        raise ValidationError("Give a reason when rejecting an order.")

    with db.connection(db_path) as conn:
        with db.write_transaction(conn):
            order = conn.execute(
                "SELECT id, customer_name, status FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if order is None:
                raise NotFound(f"No order #{order_id} found.")
            if act.role == CUSTOMER and order["customer_name"].strip().lower() != (actor_name or "").strip().lower():
                raise InvalidTransition(f"Order #{order_id} belongs to another customer.")
            if order["status"] != act.from_status:
                raise InvalidTransition(_refusal(order_id, action, act, order["status"]))
            # Conditional update: only succeeds if nobody changed the status meanwhile (A-14).
            updated = conn.execute(
                "UPDATE orders SET status = ?, reason = COALESCE(?, reason), updated_at = ? "
                "WHERE id = ? AND status = ?",
                (act.to_status, reason, db.now(), order_id, act.from_status),
            ).rowcount
            if updated != 1:
                raise InvalidTransition(f"Order #{order_id} was changed by someone else. Refresh and try again.")
    return get_order(order_id, db_path=db_path)


def _refusal(order_id: int, action: str, act: Action, current: str) -> str:
    if current == Status.COLLECTED and action == "collect":
        return f"Order #{order_id} has already been collected."
    if current == Status.COLLECTED:
        return f"Order #{order_id} is complete (Collected), so it cannot be changed."
    if current in (Status.REJECTED, Status.CANCELLED):
        return f"Order #{order_id} is closed ({current}), so it cannot be changed."
    if action == "cancel" and current in (Status.PREPARING, Status.READY):
        return f"Order #{order_id} is {current}: preparation has started, so it can no longer be cancelled."
    if action == "cancel" and current == Status.SUBMITTED:
        return f"Order #{order_id} is still awaiting confirmation. Only confirmed orders can be cancelled."
    return f"Order #{order_id} is {current}. To {act.label} it, it must be {act.from_status}."


def list_orders(slot_id: int | None = None, statuses=None, customer_name: str | None = None,
                outlet_id: int | None = None, order_id: int | None = None, db_path=None) -> list[dict]:
    """Orders with their lines, newest first. Filters are optional (FR-08, FR-09)."""
    where, params = [], []
    if order_id is not None:
        where.append("o.id = ?")
        params.append(order_id)
    if slot_id is not None:
        where.append("o.slot_id = ?")
        params.append(slot_id)
    if statuses:
        where.append(f"o.status IN ({', '.join('?' for _ in statuses)})")
        params.extend(statuses)
    if customer_name is not None:
        where.append("lower(trim(o.customer_name)) = lower(trim(?))")
        params.append(customer_name)
    if outlet_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM order_item oi JOIN menu_item m ON m.id = oi.item_id "
            "WHERE oi.order_id = o.id AND m.outlet_id = ?)"
        )
        params.append(outlet_id)
    sql = (
        "SELECT o.id, o.customer_name, o.slot_id, o.status, o.reason, o.created_at, o.updated_at, "
        "s.slot_date, s.start_time, s.end_time "
        "FROM orders o JOIN pickup_slot s ON s.id = o.slot_id"
        + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY o.id DESC"
    )
    with db.connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        ids = [row["id"] for row in rows]
        lines = conn.execute(
            "SELECT oi.order_id, m.name, oi.qty, ou.name AS outlet "
            "FROM order_item oi JOIN menu_item m ON m.id = oi.item_id JOIN outlet ou ON ou.id = m.outlet_id "
            f"WHERE oi.order_id IN ({', '.join('?' for _ in ids)}) ORDER BY m.name",
            ids,
        ).fetchall() if ids else []
    items_by_order: dict[int, list[dict]] = {}
    for line in lines:
        items_by_order.setdefault(line["order_id"], []).append(
            {"name": line["name"], "qty": line["qty"], "outlet": line["outlet"]}
        )
    return [
        {**dict(row), "slot_label": inventory.slot_label(row), "items": items_by_order.get(row["id"], [])}
        for row in rows
    ]


def get_order(order_id: int, db_path=None) -> dict:
    found = list_orders(order_id=order_id, db_path=db_path)
    if not found:
        raise NotFound(f"No order #{order_id} found.")
    return found[0]
