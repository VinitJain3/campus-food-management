"""Initial business data from the challenge PDF ("Initial Campus Menu Data").

This is the single place to check against the PDF. Tests use it too.
"""

# Five outlets, one initial menu item each (team brief, Prompt 6).
OUTLETS = ["Coffee", "Fast Food", "Main Meal", "Pure Veg", "Healthy Food"]

# Name, category and quantity per pickup slot exactly as in the PDF.
MENU_ITEMS = [
    {"name": "Veg Sandwich", "category": "Snacks", "outlet": "Fast Food", "qty_per_slot": 20},
    {"name": "Masala Dosa", "category": "South Indian", "outlet": "Pure Veg", "qty_per_slot": 15},
    {"name": "Paneer Rice Bowl", "category": "Meals", "outlet": "Main Meal", "qty_per_slot": 12},
    {"name": "Cold Coffee", "category": "Beverages", "outlet": "Coffee", "qty_per_slot": 18},
    {"name": "Fruit Bowl", "category": "Healthy Meals", "outlet": "Healthy Food", "qty_per_slot": 10},
]

# The PDF names two 30-minute windows. They are created on 4 Aug 2026 (the date
# the PDF's conditions apply to) and 5 Aug 2026 (to show those conditions do not
# carry over to other dates) - assumption A-04.
SLOTS = [
    ("2026-08-04", "12:30", "13:00"),
    ("2026-08-04", "13:00", "13:30"),
    ("2026-08-05", "12:30", "13:00"),
    ("2026-08-05", "13:00", "13:30"),
]

# "Cold Coffee: temporarily unavailable for all pickup slots on 4 Aug 2026."
# slot_start None = every slot that date. The PDF gives no reason, so the
# generic "other operational restriction" is used (DA-04, proposed).
RESTRICTIONS = [
    {"item": "Cold Coffee", "date": "2026-08-04", "slot_start": None, "reason": "OPERATIONAL"},
]

# Date-specific commitments, stored as Confirmed orders from a placeholder
# customer so they follow the same availability rules as any order (A-03).
SEED_CUSTOMER = "Pre-existing (seed)"
SEED_COMMITMENTS = [
    {"date": "2026-08-04", "start": "13:00", "item": "Veg Sandwich", "qty": 8},
    {"date": "2026-08-04", "start": "12:30", "item": "Paneer Rice Bowl", "qty": 5},
    {"date": "2026-08-04", "start": "13:00", "item": "Fruit Bowl", "qty": 4},
]
