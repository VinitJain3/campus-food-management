import pytest

from campus_food import db, inventory, orders, seed_data

PDF_ITEMS = {item["name"] for item in seed_data.MENU_ITEMS if item.get("pdf")}


class Shop:
    """Test helper: look things up by name instead of id, against one test database."""

    def __init__(self, db_path):
        self.db_path = db_path

    def slot(self, slot_date: str, start: str) -> int:
        with db.connection(self.db_path) as conn:
            return conn.execute(
                "SELECT id FROM pickup_slot WHERE slot_date = ? AND start_time = ?", (slot_date, start)
            ).fetchone()["id"]

    def item(self, name: str) -> int:
        with db.connection(self.db_path) as conn:
            return conn.execute("SELECT id FROM menu_item WHERE name = ?", (name,)).fetchone()["id"]

    def availability(self, slot_id: int) -> dict[str, inventory.ItemAvailability]:
        with db.connection(self.db_path) as conn:
            return {item.name: item for item in inventory.get_availability(conn, slot_id)}

    def available(self, slot_id: int) -> dict[str, int]:
        return {name: item.available for name, item in self.availability(slot_id).items()}

    def pdf_available(self, slot_id: int) -> dict[str, int]:
        """Availability of the five challenge items only."""
        return {name: qty for name, qty in self.available(slot_id).items() if name in PDF_ITEMS}

    def checkout(self, customer: str, slot_id: int, quantities: dict[str, int]) -> orders.Checkout:
        cart = {self.item(name): qty for name, qty in quantities.items()}
        return orders.submit_order(customer, slot_id, cart, db_path=self.db_path)

    def order(self, customer: str, slot_id: int, quantities: dict[str, int]):
        """The new order id, or a list of ids when the cart spans several outlets."""
        ids = self.checkout(customer, slot_id, quantities).order_ids
        return ids[0] if len(ids) == 1 else list(ids)

    def staff(self, order_id: int, *actions: str, reason: str | None = None, prep_minutes: int | None = None) -> dict:
        result = None
        for action in actions:
            result = orders.transition(order_id, action, orders.STAFF, reason=reason,
                                       prep_minutes=prep_minutes if action in ("accept", "confirm") else None,
                                       db_path=self.db_path)
        return result

    def cancel(self, order_id: int, customer: str) -> dict:
        return orders.transition(order_id, "cancel", orders.CUSTOMER, actor_name=customer, db_path=self.db_path)

    def status(self, order_id: int) -> str:
        return orders.get_order(order_id, db_path=self.db_path)["status"]

    def order_count(self) -> int:
        with db.connection(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    return path


@pytest.fixture
def shop(db_path):
    return Shop(db_path)


@pytest.fixture
def aug4_1230(shop):
    return shop.slot("2026-08-04", "12:30")


@pytest.fixture
def aug4_1300(shop):
    return shop.slot("2026-08-04", "13:00")


@pytest.fixture
def aug5_1230(shop):
    return shop.slot("2026-08-05", "12:30")


@pytest.fixture
def aug5_1300(shop):
    return shop.slot("2026-08-05", "13:00")
