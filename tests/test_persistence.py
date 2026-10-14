"""Restart, seed-once, reset and database constraints (FR-18, NFR-07, BRD section 9)."""

import sqlite3

import pytest

from campus_food import db, seed_data
from campus_food.status import ALL_STATUSES, Status


def _counts(db_path):
    with db.connection(db_path) as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("outlet", "menu_item", "item_option", "pickup_slot", "item_restriction", "orders",
                          "order_item")
        }


# 3 challenge commitments + 9 demo orders (17 lines); 15 menu items; 10 slots.
SEEDED = {"outlet": 5, "menu_item": 15,
          "item_option": sum(len(item["options"]) for item in seed_data.MENU_ITEMS),
          "pickup_slot": 10, "item_restriction": 1, "orders": 12, "order_item": 17}


def test_seed_loads_once(db_path):
    assert _counts(db_path) == SEEDED
    db.init_db(db_path)  # second start-up
    assert _counts(db_path) == SEEDED


def test_ac18_orders_survive_a_restart(shop, aug4_1300, db_path):
    order_id = shop.order("Asha", aug4_1300, {"Fruit Bowl": 2})
    shop.staff(order_id, "confirm")
    db.init_db(db_path)  # what app start-up does
    assert shop.status(order_id) == Status.CONFIRMED
    assert shop.available(aug4_1300)["Fruit Bowl"] == 4


def test_ac19_reset_restores_the_seed_figures(shop, aug4_1300, db_path):
    shop.order("Asha", aug4_1300, {"Fruit Bowl": 6})
    db.reset_db(db_path)
    assert _counts(db_path) == SEEDED
    assert shop.available(aug4_1300)["Fruit Bowl"] == 6
    new_id = shop.order("Ben", aug4_1300, {"Fruit Bowl": 1})
    assert new_id == 13  # order numbering restarts after the twelve seeded orders


@pytest.mark.parametrize("sql", [
    "INSERT INTO order_item (order_id, item_id, qty, unit_price_paise) VALUES (1, 2, 0, 100)",
    "INSERT INTO order_item (order_id, item_id, qty, unit_price_paise) VALUES (1, 999, 1, 100)",
    "UPDATE orders SET total_paise = total_paise + 1 WHERE id = 1",
    "UPDATE orders SET payment_method = 'Card' WHERE id = 1",
    "UPDATE orders SET prep_minutes = 0 WHERE id = 1",
    "UPDATE orders SET status = 'Lost' WHERE id = 1",
    "INSERT INTO orders (checkout_id, customer_name, outlet_id, slot_id, status, subtotal_paise, tax_paise, "
    "fee_paise, total_paise, payment_status, created_at, updated_at) "
    "VALUES ('X', '  ', 1, 1, 'Placed', 0, 0, 0, 0, 'Pending', 'x', 'x')",
    "INSERT INTO pickup_slot (slot_date, start_time, end_time) VALUES ('2026-08-04', '12:30', '13:00')",
])
def test_database_constraints_reject_bad_rows(db_path, sql):
    with db.connection(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql)


def test_schema_status_check_matches_the_lifecycle(db_path):
    with db.connection(db_path) as conn:
        for status in ALL_STATUSES:
            conn.execute("UPDATE orders SET status = ? WHERE id = 1", (status,))


def test_database_from_an_older_schema_is_rebuilt(tmp_path):
    path = tmp_path / "old.db"
    with db.connection(path) as conn:  # the first prototype's schema, user_version 0
        conn.executescript("""
            CREATE TABLE outlet (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
            CREATE TABLE menu_item (id INTEGER PRIMARY KEY, name TEXT, category TEXT, outlet_id INTEGER,
                                    qty_per_slot INTEGER);
            INSERT INTO outlet (name) VALUES ('Old');
            INSERT INTO menu_item (name, category, outlet_id, qty_per_slot) VALUES ('Old item', 'x', 1, 1);
        """)
    db.init_db(path)
    assert _counts(path) == SEEDED
    with db.connection(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
