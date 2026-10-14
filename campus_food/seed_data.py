"""Initial business data.

The five items marked `pdf=True`, their quantities per pickup slot and the
4 Aug 2026 conditions come from the challenge PDF ("Initial Campus Menu Data")
and must not change. Everything else (outlet details, prices, extra items,
demo customers and orders) is realistic demo data, which the PDF allows
("Teams may add reasonable details or additional sample records").
Demo orders use only the extra items, so the PDF figures stay exact.
"""

OUTLETS = [
    {"name": "Coffee", "cuisine": "Café · Beverages", "opens": "08:00", "closes": "18:00",
     "rating": 4.5, "reviews": 312, "tagline": "Cold brews, chai and fresh bakes", "emoji": "☕️",
     "colours": ("#7C4A2D", "#E8B98A")},
    {"name": "Fast Food", "cuisine": "Snacks · Burgers", "opens": "10:00", "closes": "21:00",
     "rating": 4.2, "reviews": 488, "tagline": "Toasties, burgers and fries", "emoji": "🍔",
     "colours": ("#C2410C", "#FDBA74")},
    {"name": "Main Meal", "cuisine": "North Indian · Meals", "opens": "11:30", "closes": "15:30",
     "rating": 4.4, "reviews": 276, "tagline": "Rice bowls and full thalis", "emoji": "🍛",
     "colours": ("#A16207", "#FDE68A")},
    {"name": "Pure Veg", "cuisine": "South Indian · Pure veg", "opens": "07:30", "closes": "15:00",
     "rating": 4.6, "reviews": 529, "tagline": "Crisp dosas and filter coffee", "emoji": "🌿",
     "colours": ("#15803D", "#BBF7D0")},
    {"name": "Healthy Food", "cuisine": "Salads · Fresh fruit", "opens": "08:00", "closes": "17:00",
     "rating": 4.3, "reviews": 198, "tagline": "Fruit bowls, sprouts and coolers", "emoji": "🥗",
     "colours": ("#0F766E", "#99F6E4")},
]

# price in rupees; options are (label, extra price in rupees).
MENU_ITEMS = [
    # --- Coffee ---------------------------------------------------------------------------
    {"name": "Cold Coffee", "category": "Beverages", "outlet": "Coffee", "qty_per_slot": 18, "pdf": True,
     "price": 80, "prep_minutes": 5, "emoji": "🧋", "tags": ["Veg"],
     "description": "Slow-steeped coffee shaken with chilled milk and ice.",
     "ingredients": "Coffee, milk, sugar, ice",
     "options": [("Less sugar", 0), ("Extra shot", 20), ("Oat milk", 30)]},
    {"name": "Masala Chai", "category": "Beverages", "outlet": "Coffee", "qty_per_slot": 30,
     "price": 30, "prep_minutes": 4, "emoji": "🍵", "tags": ["Veg"],
     "description": "Strong tea brewed with ginger, cardamom and milk.",
     "ingredients": "Tea, milk, ginger, cardamom, sugar",
     "options": [("Less sugar", 0), ("Extra ginger", 0)]},
    {"name": "Chocolate Muffin", "category": "Bakery", "outlet": "Coffee", "qty_per_slot": 15,
     "price": 60, "prep_minutes": 2, "emoji": "🧁", "tags": ["Contains egg"],
     "description": "Soft chocolate muffin with a molten centre, baked every morning.",
     "ingredients": "Flour, cocoa, egg, butter, sugar, dark chocolate",
     "options": [("Warm it up", 0)]},
    # --- Fast Food ------------------------------------------------------------------------
    {"name": "Veg Sandwich", "category": "Snacks", "outlet": "Fast Food", "qty_per_slot": 20, "pdf": True,
     "price": 60, "prep_minutes": 8, "emoji": "🥪", "tags": ["Veg"],
     "description": "Grilled sandwich layered with vegetables and mint chutney.",
     "ingredients": "Bread, potato, cucumber, tomato, onion, mint chutney, butter",
     "options": [("Extra cheese", 15), ("No onion", 0), ("Toasted extra crisp", 0)]},
    {"name": "Veg Burger", "category": "Snacks", "outlet": "Fast Food", "qty_per_slot": 15,
     "price": 90, "prep_minutes": 10, "emoji": "🍔", "tags": ["Veg"],
     "description": "Crunchy vegetable patty with lettuce, tomato and house sauce.",
     "ingredients": "Bun, vegetable patty, lettuce, tomato, onion, sauce",
     "options": [("Extra cheese", 15), ("No onion", 0)]},
    {"name": "French Fries", "category": "Snacks", "outlet": "Fast Food", "qty_per_slot": 25,
     "price": 70, "prep_minutes": 7, "emoji": "🍟", "tags": ["Vegan"],
     "description": "Golden fries, salted and served hot.",
     "ingredients": "Potato, sunflower oil, salt",
     "options": [("Peri-peri seasoning", 10)]},
    # --- Main Meal ------------------------------------------------------------------------
    {"name": "Paneer Rice Bowl", "category": "Meals", "outlet": "Main Meal", "qty_per_slot": 12, "pdf": True,
     "price": 140, "prep_minutes": 15, "emoji": "🍛", "tags": ["Veg", "High protein"],
     "description": "Paneer tikka masala over jeera rice with a side of salad.",
     "ingredients": "Paneer, rice, tomato, onion, cream, spices",
     "options": [("Extra paneer", 40), ("Less spicy", 0)]},
    {"name": "Rajma Chawal", "category": "Meals", "outlet": "Main Meal", "qty_per_slot": 15,
     "price": 110, "prep_minutes": 12, "emoji": "🍲", "tags": ["Vegan", "Gluten-free"],
     "description": "Slow-cooked kidney bean curry with steamed basmati rice.",
     "ingredients": "Kidney beans, rice, tomato, onion, garlic, spices",
     "options": [("Less spicy", 0), ("Extra rice", 20)]},
    {"name": "Veg Thali", "category": "Meals", "outlet": "Main Meal", "qty_per_slot": 10,
     "price": 150, "prep_minutes": 15, "emoji": "🍱", "tags": ["Veg"],
     "description": "Two curries, dal, rice, two rotis, salad and a sweet.",
     "ingredients": "Seasonal vegetables, lentils, rice, wheat, yogurt",
     "options": [("Extra roti", 15)]},
    # --- Pure Veg -------------------------------------------------------------------------
    {"name": "Masala Dosa", "category": "South Indian", "outlet": "Pure Veg", "qty_per_slot": 15, "pdf": True,
     "price": 70, "prep_minutes": 10, "emoji": "🫓", "tags": ["Veg", "Gluten-free"],
     "description": "Crisp rice-lentil crêpe filled with spiced potato, with sambar and chutney.",
     "ingredients": "Rice, urad dal, potato, onion, mustard seeds, curry leaves",
     "options": [("Ghee roast", 15), ("Extra chutney", 0)]},
    {"name": "Idli Vada", "category": "South Indian", "outlet": "Pure Veg", "qty_per_slot": 20,
     "price": 50, "prep_minutes": 6, "emoji": "🍘", "tags": ["Vegan"],
     "description": "Two steamed idlis and a crisp medu vada with sambar.",
     "ingredients": "Rice, urad dal, lentils, spices",
     "options": [("Extra sambar", 0)]},
    {"name": "Filter Coffee", "category": "Beverages", "outlet": "Pure Veg", "qty_per_slot": 30,
     "price": 25, "prep_minutes": 3, "emoji": "☕️", "tags": ["Veg"],
     "description": "South Indian decoction coffee frothed with hot milk.",
     "ingredients": "Coffee, chicory, milk, sugar",
     "options": [("Less sugar", 0)]},
    # --- Healthy Food ---------------------------------------------------------------------
    {"name": "Fruit Bowl", "category": "Healthy Meals", "outlet": "Healthy Food", "qty_per_slot": 10, "pdf": True,
     "price": 90, "prep_minutes": 5, "emoji": "🍓", "tags": ["Vegan", "Gluten-free"],
     "description": "Seasonal cut fruit with a squeeze of lime and chaat masala.",
     "ingredients": "Papaya, watermelon, apple, banana, pomegranate, lime",
     "options": [("Add yogurt", 20), ("No banana", 0)]},
    {"name": "Sprouts Salad", "category": "Healthy Meals", "outlet": "Healthy Food", "qty_per_slot": 12,
     "price": 80, "prep_minutes": 6, "emoji": "🥗", "tags": ["Vegan", "High protein"],
     "description": "Moong sprouts tossed with cucumber, tomato, peanuts and lemon.",
     "ingredients": "Moong sprouts, cucumber, tomato, onion, peanuts, lemon",
     "options": [("No onion", 0), ("Add paneer", 30)]},
    {"name": "Fresh Lime Soda", "category": "Beverages", "outlet": "Healthy Food", "qty_per_slot": 25,
     "price": 40, "prep_minutes": 3, "emoji": "🍋", "tags": ["Vegan"],
     "description": "Fizzy lime cooler, made sweet or salted.",
     "ingredients": "Lime, soda, sugar or black salt, mint",
     "options": [("Salted", 0), ("Sweet", 0)]},
]

# The PDF names two 30-minute windows (12:30-13:00, 13:00-13:30). They exist on
# 4 Aug 2026 (where the PDF's conditions apply) and 5 Aug 2026 (to show those
# conditions do not carry over) - A-04. 12:00 and 13:30 are extra demo windows.
# 3 Aug 2026 holds demo order history only; customers order for ORDER_DATES.
ORDER_DATES = ["2026-08-04", "2026-08-05"]
SLOTS = [
    ("2026-08-03", "12:30", "13:00"),
    ("2026-08-03", "13:00", "13:30"),
    ("2026-08-04", "12:00", "12:30"),
    ("2026-08-04", "12:30", "13:00"),
    ("2026-08-04", "13:00", "13:30"),
    ("2026-08-04", "13:30", "14:00"),
    ("2026-08-05", "12:00", "12:30"),
    ("2026-08-05", "12:30", "13:00"),
    ("2026-08-05", "13:00", "13:30"),
    ("2026-08-05", "13:30", "14:00"),
]

# "Cold Coffee: temporarily unavailable for all pickup slots on 4 Aug 2026."
# slot_start None = every slot that date. The PDF gives no reason, so the
# generic "operational restriction" is used (DA-04, proposed).
RESTRICTIONS = [
    {"item": "Cold Coffee", "date": "2026-08-04", "slot_start": None, "reason": "OPERATIONAL"},
]

# Date-specific commitments from the PDF, stored as Accepted orders from a
# placeholder customer so they follow the same availability rules (A-03).
SEED_CUSTOMER = "Pre-existing (seed)"
SEED_COMMITMENTS = [
    {"date": "2026-08-04", "start": "13:00", "item": "Veg Sandwich", "qty": 8},
    {"date": "2026-08-04", "start": "12:30", "item": "Paneer Rice Bowl", "qty": 5},
    {"date": "2026-08-04", "start": "13:00", "item": "Fruit Bowl", "qty": 4},
]

# Pricing rules for the demo (prices in the menu are before tax).
TAX_RATE_PERCENT = 5        # GST on restaurant food
PICKUP_FEE_RUPEES = 5       # packaging and pickup fee, per outlet order

# The demo customer the customer app starts as; their order history is below.
DEMO_CUSTOMER = {"name": "Asha Rao", "phone": "98450 12345"}

# Demo orders. Only extra (non-PDF) items, so the PDF availability is untouched.
# minutes_ago: when the order was placed (None = on the history date, 3 Aug).
DEMO_ORDERS = [
    {"customer": "Asha Rao", "phone": "98450 12345", "date": "2026-08-03", "start": "12:30",
     "lines": [("Veg Burger", 1), ("French Fries", 1)], "status": "Completed",
     "payment": "UPI", "prep": 10, "minutes_ago": None},
    {"customer": "Asha Rao", "phone": "98450 12345", "date": "2026-08-03", "start": "13:00",
     "lines": [("Masala Chai", 2), ("Chocolate Muffin", 1)], "status": "Completed",
     "payment": "Cash on Delivery", "prep": 5, "minutes_ago": None},
    {"customer": "Asha Rao", "phone": "98450 12345", "date": "2026-08-03", "start": "13:00",
     "lines": [("Sprouts Salad", 1)], "status": "Rejected", "reason": "Sprouts delivery missed this morning",
     "payment": "UPI", "prep": None, "minutes_ago": None},
    {"customer": "Asha Rao", "phone": "98450 12345", "date": "2026-08-05", "start": "12:30",
     "lines": [("Rajma Chawal", 1)], "status": "Preparing",
     "payment": "Cash on Delivery", "prep": 15, "minutes_ago": 9},
    {"customer": "Rohan Mehta", "phone": "99001 22334", "date": "2026-08-05", "start": "12:30",
     "lines": [("Veg Burger", 2), ("French Fries", 1)], "status": "Placed",
     "payment": "UPI", "prep": None, "minutes_ago": 3},
    {"customer": "Priya Nair", "phone": "90080 45671", "date": "2026-08-05", "start": "13:00",
     "lines": [("Sprouts Salad", 1), ("Fresh Lime Soda", 2)], "status": "Placed",
     "payment": "Cash on Delivery", "prep": None, "minutes_ago": 6},
    {"customer": "Kiran Das", "phone": "97411 67890", "date": "2026-08-05", "start": "13:00",
     "lines": [("Idli Vada", 2), ("Filter Coffee", 2)], "status": "Accepted",
     "payment": "UPI", "prep": 12, "minutes_ago": 14},
    {"customer": "Meera Iyer", "phone": "98860 33445", "date": "2026-08-05", "start": "12:00",
     "lines": [("Masala Chai", 1)], "status": "Ready",
     "payment": "Cash on Delivery", "prep": 5, "minutes_ago": 21},
    {"customer": "Arjun Singh", "phone": "96630 55667", "date": "2026-08-05", "start": "12:30",
     "lines": [("Veg Thali", 1)], "status": "Delivered",
     "payment": "UPI", "prep": 15, "minutes_ago": 32},
]
