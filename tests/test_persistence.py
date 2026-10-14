"""Restart, seed-once, reset and database constraints (FR-18, NFR-07, BRD section 9)."""

import sqlite3

import pytest

from campus_food import db
from campus_food.status import ALL_STATUSES, Status


def _counts(db_path):
    with db.connection(db_path) as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("outlet", "menu_item", "pickup_slot", "item_restriction", "orders", "order_item")
        }


SEEDED = {"outlet": 5, "menu_item": 5, "pickup_slot": 4, "item_restriction": 1, "orders": 3, "order_item": 3}


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
    assert new_id == 4  # order numbering restarts after the three seed orders


@pytest.mark.parametrize("sql", [
    "INSERT INTO order_item (order_id, item_id, qty) VALUES (1, 1, 0)",
    "INSERT INTO order_item (order_id, item_id, qty) VALUES (1, 999, 1)",
    "UPDATE orders SET status = 'Lost' WHERE id = 1",
    "INSERT INTO orders (customer_name, slot_id, status, created_at, updated_at) VALUES ('  ', 1, 'Submitted', 'x', 'x')",
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
