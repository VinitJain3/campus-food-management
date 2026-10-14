"""Outlets, menu, pickup slots and availability (BRD sections 6 and 7).

Availability is always calculated from orders, never stored as a counter:

    available(item, slot) = 0                                if the item is restricted for the slot
                          = qty_per_slot - sum(counted qty)   otherwise

Reserving is inserting an order's lines; releasing is the order leaving a
COUNTED status. Accepting or preparing changes nothing here, so stock is never
reserved or released twice.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date

from . import seed_data
from .errors import LineFailure, NotFound
from .status import COUNTED

AVAILABLE = "available"
SOLD_OUT = "sold out"
RESTRICTED = "unavailable"

# Below this many units the menu shows "Only N left".
LOW_STOCK = 5

REASON_LABELS = {
    "SOLD_OUT": "sold out",
    "CANNOT_PREPARE": "cannot be prepared",
    "INGREDIENT_SHORTAGE": "ingredient shortage",
    "OPERATIONAL": "operational restriction",
}


@dataclass(frozen=True)
class ItemAvailability:
    item_id: int
    name: str
    category: str
    outlet_id: int
    outlet: str
    capacity: int
    used: int
    available: int
    state: str  # AVAILABLE, SOLD_OUT or RESTRICTED
    restriction: str | None  # human-readable reason when RESTRICTED


def list_outlets(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM outlet ORDER BY name")]


def get_outlet(conn: sqlite3.Connection, outlet_id: int) -> dict:
    row = conn.execute("SELECT * FROM outlet WHERE id = ?", (outlet_id,)).fetchone()
    if row is None:
        raise NotFound(f"Outlet {outlet_id} does not exist.")
    return dict(row)


def list_menu(conn: sqlite3.Connection, outlet_id: int | None = None) -> list[dict]:
    """Menu items with their outlet, tags and customisation options."""
    sql = ("SELECT m.*, o.name AS outlet FROM menu_item m JOIN outlet o ON o.id = m.outlet_id"
           + (" WHERE m.outlet_id = ?" if outlet_id is not None else "") + " ORDER BY o.name, m.id")
    rows = conn.execute(sql, (outlet_id,) if outlet_id is not None else ()).fetchall()
    options: dict[int, list[dict]] = {}
    for row in conn.execute("SELECT item_id, label, price_paise FROM item_option ORDER BY id"):
        options.setdefault(row["item_id"], []).append({"label": row["label"], "price_paise": row["price_paise"]})
    return [
        {**dict(row), "tags": [tag for tag in row["tags"].split(",") if tag], "options": options.get(row["id"], [])}
        for row in rows
    ]


def list_slots(conn: sqlite3.Connection, orderable_only: bool = False) -> list[sqlite3.Row]:
    """All pickup slots; `orderable_only` keeps the dates customers order for
    (the history-only date is left out)."""
    rows = conn.execute(
        "SELECT id, slot_date, start_time, end_time FROM pickup_slot ORDER BY slot_date, start_time"
    ).fetchall()
    if orderable_only:
        rows = [row for row in rows if row["slot_date"] in seed_data.ORDER_DATES]
    return rows


def get_slot(conn: sqlite3.Connection, slot_id: int) -> sqlite3.Row:
    slot = conn.execute(
        "SELECT id, slot_date, start_time, end_time FROM pickup_slot WHERE id = ?", (slot_id,)
    ).fetchone()
    if slot is None:
        raise NotFound(f"Pickup slot {slot_id} does not exist.")
    return slot


def slot_label(slot) -> str:
    day = date.fromisoformat(slot["slot_date"])
    return f"{day:%a} {day.day} {day:%b %Y}, {slot['start_time']}-{slot['end_time']}"


def get_availability(conn: sqlite3.Connection, slot_id: int) -> list[ItemAvailability]:
    """Availability of every menu item for one pickup slot (FR-03, INV-01)."""
    slot = get_slot(conn, slot_id)
    counted = sorted(COUNTED)
    placeholders = ", ".join("?" for _ in counted)
    rows = conn.execute(
        f"""
        SELECT m.id, m.name, m.category, o.id AS outlet_id, o.name AS outlet, m.qty_per_slot,
               COALESCE((SELECT SUM(oi.qty)
                           FROM order_item oi JOIN orders ord ON ord.id = oi.order_id
                          WHERE oi.item_id = m.id
                            AND ord.slot_id = ?
                            AND ord.status IN ({placeholders})), 0) AS used,
               (SELECT r.reason FROM item_restriction r
                 WHERE r.item_id = m.id
                   AND r.restriction_date = ?
                   AND (r.slot_id IS NULL OR r.slot_id = ?)
                 ORDER BY r.id LIMIT 1) AS restriction
          FROM menu_item m JOIN outlet o ON o.id = m.outlet_id
         ORDER BY o.name, m.id
        """,
        (slot_id, *counted, slot["slot_date"], slot_id),
    ).fetchall()

    result = []
    for row in rows:
        remaining = max(row["qty_per_slot"] - row["used"], 0)
        if row["restriction"]:
            state, available = RESTRICTED, 0
            reason = REASON_LABELS.get(row["restriction"], row["restriction"])
        else:
            state = AVAILABLE if remaining > 0 else SOLD_OUT
            available, reason = remaining, None
        result.append(ItemAvailability(
            item_id=row["id"], name=row["name"], category=row["category"], outlet_id=row["outlet_id"],
            outlet=row["outlet"], capacity=row["qty_per_slot"], used=row["used"], available=available,
            state=state, restriction=reason,
        ))
    return result


def check_lines(conn: sqlite3.Connection, slot_id: int, lines: dict[int, int]) -> list[LineFailure]:
    """Every line that cannot be fulfilled in full. An empty list means the
    complete order fits (BC-3, BC-4, INV-03). Never partial: callers reserve all
    lines or none. `lines` maps item id to the total quantity across the cart."""
    by_id = {item.item_id: item for item in get_availability(conn, slot_id)}
    failures = []
    for item_id, qty in lines.items():
        item = by_id[item_id]
        if item.state == RESTRICTED:
            failures.append(LineFailure(item.name, qty, 0, item.restriction))
        elif qty > item.available:
            failures.append(LineFailure(item.name, qty, item.available))
    return failures
