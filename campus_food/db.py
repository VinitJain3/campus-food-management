"""SQLite persistence: connections, schema, seeding, reset and write transactions."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from . import seed_data
from .errors import PersistenceError
from .status import ALL_STATUSES, Status

DEFAULT_DB_PATH = Path(
    os.environ.get("CAMPUS_FOOD_DB", Path(__file__).resolve().parent.parent / "campus_food.db")
)

# Bump when the schema changes: an older local database is rebuilt from the seed.
SCHEMA_VERSION = 2

# How long a writer waits for another writer's lock before giving up (DA-05).
BUSY_TIMEOUT_SECONDS = 5.0

RESTRICTION_REASONS = ("SOLD_OUT", "CANNOT_PREPARE", "INGREDIENT_SHORTAGE", "OPERATIONAL")
PAYMENT_METHODS = ("Cash on Delivery", "UPI")
PAYMENT_STATUSES = ("Pending", "Pay at pickup", "Paid", "Refunded")

TABLES = ("order_event", "order_item", "orders", "item_restriction", "item_option",
          "pickup_slot", "menu_item", "outlet")


def _in_list(values) -> str:
    return ", ".join(f"'{value}'" for value in values)


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS outlet (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    cuisine  TEXT NOT NULL,
    opens    TEXT NOT NULL,
    closes   TEXT NOT NULL,
    rating   REAL NOT NULL CHECK (rating BETWEEN 0 AND 5),
    reviews  INTEGER NOT NULL CHECK (reviews >= 0),
    tagline  TEXT NOT NULL,
    emoji    TEXT NOT NULL,
    colour_a TEXT NOT NULL,
    colour_b TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS menu_item (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    category     TEXT NOT NULL,
    outlet_id    INTEGER NOT NULL REFERENCES outlet(id),
    qty_per_slot INTEGER NOT NULL CHECK (qty_per_slot >= 0),
    price_paise  INTEGER NOT NULL CHECK (price_paise >= 0),
    prep_minutes INTEGER NOT NULL CHECK (prep_minutes > 0),
    description  TEXT NOT NULL,
    ingredients  TEXT NOT NULL,
    tags         TEXT NOT NULL,
    emoji        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_option (
    id          INTEGER PRIMARY KEY,
    item_id     INTEGER NOT NULL REFERENCES menu_item(id),
    label       TEXT NOT NULL,
    price_paise INTEGER NOT NULL CHECK (price_paise >= 0),
    UNIQUE (item_id, label)
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
    reason           TEXT NOT NULL CHECK (reason IN ({_in_list(RESTRICTION_REASONS)}))
);

CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    checkout_id    TEXT NOT NULL,
    customer_name  TEXT NOT NULL CHECK (length(trim(customer_name)) > 0),
    customer_phone TEXT,
    outlet_id      INTEGER NOT NULL REFERENCES outlet(id),
    slot_id        INTEGER NOT NULL REFERENCES pickup_slot(id),
    status         TEXT NOT NULL CHECK (status IN ({_in_list(ALL_STATUSES)})),
    reason         TEXT,
    prep_minutes   INTEGER CHECK (prep_minutes BETWEEN 1 AND 240),
    subtotal_paise INTEGER NOT NULL CHECK (subtotal_paise >= 0),
    tax_paise      INTEGER NOT NULL CHECK (tax_paise >= 0),
    fee_paise      INTEGER NOT NULL CHECK (fee_paise >= 0),
    total_paise    INTEGER NOT NULL CHECK (total_paise = subtotal_paise + tax_paise + fee_paise),
    payment_method TEXT CHECK (payment_method IN ({_in_list(PAYMENT_METHODS)})),
    payment_status TEXT NOT NULL CHECK (payment_status IN ({_in_list(PAYMENT_STATUSES)})),
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_item (
    id               INTEGER PRIMARY KEY,
    order_id         INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    item_id          INTEGER NOT NULL REFERENCES menu_item(id),
    qty              INTEGER NOT NULL CHECK (qty > 0),
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),
    options          TEXT NOT NULL DEFAULT '',
    UNIQUE (order_id, item_id, options)
);

CREATE TABLE IF NOT EXISTS order_event (
    id       INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    status   TEXT NOT NULL CHECK (status IN ({_in_list(ALL_STATUSES)})),
    at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_slot_status ON orders(slot_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_checkout ON orders(checkout_id);
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
    so restarts never duplicate or wipe data (FR-18, NFR-07). A database from an
    older schema version is rebuilt."""
    with connection(db_path) as conn:
        if conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            _drop_all(conn)
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        with write_transaction(conn):
            if conn.execute("SELECT COUNT(*) FROM menu_item").fetchone()[0] == 0:
                _seed(conn)


def reset_db(db_path=None) -> None:
    """Delete every order and reload the seed data (FR-18, DA-07)."""
    with connection(db_path) as conn:
        conn.executescript(SCHEMA)
        with write_transaction(conn):
            for table in TABLES:
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'orders'")
            _seed(conn)


def _drop_all(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in TABLES + ("order_line",):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute("PRAGMA foreign_keys = ON")


def _seed(conn: sqlite3.Connection) -> None:
    from . import pricing  # local import: pricing reads the tables created here

    outlet_ids = {}
    for outlet in seed_data.OUTLETS:
        outlet_ids[outlet["name"]] = conn.execute(
            "INSERT INTO outlet (name, cuisine, opens, closes, rating, reviews, tagline, emoji, colour_a, colour_b) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (outlet["name"], outlet["cuisine"], outlet["opens"], outlet["closes"], outlet["rating"],
             outlet["reviews"], outlet["tagline"], outlet["emoji"], *outlet["colours"]),
        ).lastrowid

    item_ids = {}
    for item in seed_data.MENU_ITEMS:
        item_id = conn.execute(
            "INSERT INTO menu_item (name, category, outlet_id, qty_per_slot, price_paise, prep_minutes, "
            "description, ingredients, tags, emoji) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item["name"], item["category"], outlet_ids[item["outlet"]], item["qty_per_slot"],
             item["price"] * 100, item["prep_minutes"], item["description"], item["ingredients"],
             ",".join(item["tags"]), item["emoji"]),
        ).lastrowid
        item_ids[item["name"]] = item_id
        for label, extra in item["options"]:
            conn.execute(
                "INSERT INTO item_option (item_id, label, price_paise) VALUES (?, ?, ?)",
                (item_id, label, extra * 100),
            )

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

    for number, commitment in enumerate(seed_data.SEED_COMMITMENTS, start=1):
        _insert_seed_order(
            conn, pricing, checkout_id=f"PDF-{number}", customer=seed_data.SEED_CUSTOMER, phone=None,
            slot_id=slot_ids[(commitment["date"], commitment["start"])],
            lines={item_ids[commitment["item"]]: commitment["qty"]},
            status=Status.ACCEPTED, reason="Commitment given in the challenge data",
            payment=None, prep=None, placed_at=now(),
        )

    current = datetime.now()
    for number, demo in enumerate(seed_data.DEMO_ORDERS, start=1):
        if demo["minutes_ago"] is None:
            placed = datetime.fromisoformat(f"{demo['date']}T11:{40 + len(demo['lines']):02d}:00")
        else:
            placed = current - timedelta(minutes=demo["minutes_ago"])
        _insert_seed_order(
            conn, pricing, checkout_id=f"DEMO-{number}", customer=demo["customer"], phone=demo["phone"],
            slot_id=slot_ids[(demo["date"], demo["start"])],
            lines={item_ids[name]: qty for name, qty in demo["lines"]},
            status=demo["status"], reason=demo.get("reason"), payment=demo["payment"],
            prep=demo["prep"], placed_at=placed.isoformat(timespec="seconds"),
        )


# Statuses an order passes through to reach each status (for the seeded timeline).
_PATH = {
    Status.PLACED: [Status.PLACED],
    Status.ACCEPTED: [Status.PLACED, Status.ACCEPTED],
    Status.PREPARING: [Status.PLACED, Status.ACCEPTED, Status.PREPARING],
    Status.READY: [Status.PLACED, Status.ACCEPTED, Status.PREPARING, Status.READY],
    Status.DELIVERED: [Status.PLACED, Status.ACCEPTED, Status.PREPARING, Status.READY, Status.DELIVERED],
    Status.COMPLETED: [Status.PLACED, Status.ACCEPTED, Status.PREPARING, Status.READY, Status.DELIVERED,
                       Status.COMPLETED],
    Status.REJECTED: [Status.PLACED, Status.REJECTED],
}


def _insert_seed_order(conn, pricing, *, checkout_id, customer, phone, slot_id, lines, status, reason, payment, prep,
                       placed_at):
    quote = pricing.quote(conn, [{"item_id": item_id, "qty": qty, "options": []} for item_id, qty in lines.items()])
    (outlet_quote,) = quote.outlets
    if payment is None:
        payment_status = "Pending"
    elif status == Status.REJECTED and payment == "UPI":
        payment_status = "Refunded"
    elif payment == "UPI" or status == Status.COMPLETED:
        payment_status = "Paid"
    else:
        payment_status = "Pay at pickup"
    order_id = conn.execute(
        "INSERT INTO orders (checkout_id, customer_name, customer_phone, outlet_id, slot_id, status, reason, "
        "prep_minutes, subtotal_paise, tax_paise, fee_paise, total_paise, payment_method, payment_status, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (checkout_id, customer, phone, outlet_quote.outlet_id, slot_id, status, reason, prep,
         outlet_quote.subtotal, outlet_quote.tax, outlet_quote.fee, outlet_quote.total, payment, payment_status,
         placed_at, placed_at),
    ).lastrowid
    for line in outlet_quote.lines:
        conn.execute(
            "INSERT INTO order_item (order_id, item_id, qty, unit_price_paise, options) VALUES (?, ?, ?, ?, ?)",
            (order_id, line.item_id, line.qty, line.unit_price, line.options_text),
        )
    stamp = datetime.fromisoformat(placed_at)
    for step, status_reached in enumerate(_PATH.get(status, [Status.PLACED, status])):
        conn.execute(
            "INSERT INTO order_event (order_id, status, at) VALUES (?, ?, ?)",
            (order_id, status_reached, (stamp + timedelta(minutes=3 * step)).isoformat(timespec="seconds")),
        )
