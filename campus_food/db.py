"""SQLite persistence: connections, schema, seeding, reset and write transactions."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import seed_data
from .errors import PersistenceError
from .status import ALL_STATUSES, Status

DEFAULT_DB_PATH = Path(
    os.environ.get("CAMPUS_FOOD_DB", Path(__file__).resolve().parent.parent / "campus_food.db")
)

# How long a writer waits for another writer's lock before giving up (DA-05).
BUSY_TIMEOUT_SECONDS = 5.0

RESTRICTION_REASONS = ("SOLD_OUT", "CANNOT_PREPARE", "INGREDIENT_SHORTAGE", "OPERATIONAL")

_status_list = ", ".join(f"'{status}'" for status in ALL_STATUSES)
_reason_list = ", ".join(f"'{reason}'" for reason in RESTRICTION_REASONS)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS outlet (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS menu_item (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    category     TEXT NOT NULL,
    outlet_id    INTEGER NOT NULL REFERENCES outlet(id),
    qty_per_slot INTEGER NOT NULL CHECK (qty_per_slot >= 0)
);

CREATE TABLE IF NOT EXISTS pickup_slot (
    id         INTEGER PRIMARY KEY,
    slot_date  TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time   TEXT NOT NULL,
    UNIQUE (slot_date, start_time),
    CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS item_restriction (
    id               INTEGER PRIMARY KEY,
    item_id          INTEGER NOT NULL REFERENCES menu_item(id),
    restriction_date TEXT NOT NULL,
    slot_id          INTEGER REFERENCES pickup_slot(id),
    reason           TEXT NOT NULL CHECK (reason IN ({_reason_list}))
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL CHECK (length(trim(customer_name)) > 0),
    slot_id       INTEGER NOT NULL REFERENCES pickup_slot(id),
    status        TEXT NOT NULL CHECK (status IN ({_status_list})),
    reason        TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_item (
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    item_id  INTEGER NOT NULL REFERENCES menu_item(id),
    qty      INTEGER NOT NULL CHECK (qty > 0),
    PRIMARY KEY (order_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_slot_status ON orders(slot_id, status);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(db_path=None) -> sqlite3.Connection:
    """Open a new connection. One per service call: Streamlit serves sessions on
    separate threads and SQLite connections must not be shared between threads."""
    conn = sqlite3.connect(
        db_path or DEFAULT_DB_PATH, timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection(db_path=None):
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def write_transaction(conn: sqlite3.Connection):
    """BEGIN IMMEDIATE takes SQLite's write lock up front, so a second writer waits
    instead of reading availability that is about to change (INV-08). Any error
    rolls everything back; nothing is ever half-written (ERR-12)."""
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        raise PersistenceError("The system is busy, so nothing was saved. Please try again.") from exc
    try:
        yield conn
    except sqlite3.Error as exc:
        conn.execute("ROLLBACK")
        raise PersistenceError("The change could not be saved, so nothing was changed. Please try again.") from exc
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    try:
        conn.execute("COMMIT")
    except sqlite3.Error as exc:
        conn.execute("ROLLBACK")
        raise PersistenceError("The change could not be saved, so nothing was changed. Please try again.") from exc


def init_db(db_path=None) -> None:
    """Create the schema and load the seed data, but only into an empty database,
    so restarts never duplicate or wipe data (FR-18, NFR-07)."""
    with connection(db_path) as conn:
        conn.executescript(SCHEMA)
        with write_transaction(conn):
            if conn.execute("SELECT COUNT(*) FROM menu_item").fetchone()[0] == 0:
                _seed(conn)


def reset_db(db_path=None) -> None:
    """Delete every order and reload the seed data (FR-18, DA-07)."""
    with connection(db_path) as conn:
        conn.executescript(SCHEMA)
        with write_transaction(conn):
            for table in ("order_item", "orders", "item_restriction", "pickup_slot", "menu_item", "outlet"):
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'orders'")
            _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    outlet_ids = {}
    for name in seed_data.OUTLETS:
        outlet_ids[name] = conn.execute("INSERT INTO outlet (name) VALUES (?)", (name,)).lastrowid

    item_ids = {}
    for item in seed_data.MENU_ITEMS:
        item_ids[item["name"]] = conn.execute(
            "INSERT INTO menu_item (name, category, outlet_id, qty_per_slot) VALUES (?, ?, ?, ?)",
            (item["name"], item["category"], outlet_ids[item["outlet"]], item["qty_per_slot"]),
        ).lastrowid

    slot_ids = {}
    for slot_date, start, end in seed_data.SLOTS:
        slot_ids[(slot_date, start)] = conn.execute(
            "INSERT INTO pickup_slot (slot_date, start_time, end_time) VALUES (?, ?, ?)",
            (slot_date, start, end),
        ).lastrowid

    for restriction in seed_data.RESTRICTIONS:
        slot_id = slot_ids[(restriction["date"], restriction["slot_start"])] if restriction["slot_start"] else None
        conn.execute(
            "INSERT INTO item_restriction (item_id, restriction_date, slot_id, reason) VALUES (?, ?, ?, ?)",
            (item_ids[restriction["item"]], restriction["date"], slot_id, restriction["reason"]),
        )

    timestamp = now()
    for commitment in seed_data.SEED_COMMITMENTS:
        order_id = conn.execute(
            "INSERT INTO orders (customer_name, slot_id, status, reason, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                seed_data.SEED_CUSTOMER,
                slot_ids[(commitment["date"], commitment["start"])],
                Status.CONFIRMED,
                "Commitment given in the challenge data",
                timestamp,
                timestamp,
            ),
        ).lastrowid
        conn.execute(
            "INSERT INTO order_item (order_id, item_id, qty) VALUES (?, ?, ?)",
            (order_id, item_ids[commitment["item"]], commitment["qty"]),
        )
