"""Cart normalisation and pricing: one place that turns cart lines into money.

Used by the cart screen (to show the bill), by checkout (to store the bill on
each order) and by the seed data, so the three can never disagree. Amounts are
integer paise to avoid rounding drift.
"""

import sqlite3
from dataclasses import dataclass

from . import seed_data
from .errors import ValidationError


@dataclass(frozen=True)
class QuoteLine:
    item_id: int
    name: str
    emoji: str
    qty: int
    options: tuple[str, ...]
    unit_price: int  # base price + chosen options, paise
    line_total: int

    @property
    def options_text(self) -> str:
        return ", ".join(self.options)


@dataclass(frozen=True)
class OutletQuote:
    outlet_id: int
    outlet_name: str
    lines: tuple[QuoteLine, ...]
    subtotal: int
    tax: int
    fee: int
    total: int
    prep_minutes: int  # estimate: the slowest item in this outlet's order


@dataclass(frozen=True)
class Quote:
    outlets: tuple[OutletQuote, ...]
    subtotal: int
    tax: int
    fee: int
    total: int


def tax_on(subtotal_paise: int) -> int:
    """GST at TAX_RATE_PERCENT, rounded half-up to the paisa."""
    return (subtotal_paise * seed_data.TAX_RATE_PERCENT + 50) // 100


def normalise_cart(cart) -> list[dict]:
    """Accepts {item_id: qty}, [(item_id, qty), ...] or [{"item_id", "qty", "options"}, ...].
    Lines for the same item with the same options are merged (FR-04). Quantities
    must be whole numbers of at least 1."""
    if isinstance(cart, dict):
        raw = [{"item_id": item_id, "qty": qty, "options": []} for item_id, qty in cart.items()]
    else:
        raw = [line if isinstance(line, dict) else {"item_id": line[0], "qty": line[1], "options": []}
               for line in cart]
    merged: dict[tuple, dict] = {}
    for line in raw:
        qty = line["qty"]
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            raise ValidationError(f"Quantity must be a whole number of 1 or more (got {qty!r}).")
        options = tuple(sorted(set(line.get("options") or ())))
        key = (line["item_id"], options)
        if key in merged:
            merged[key]["qty"] += qty
        else:
            merged[key] = {"item_id": line["item_id"], "qty": qty, "options": list(options)}
    return list(merged.values())


def quote(conn: sqlite3.Connection, cart) -> Quote:
    """Price a cart, grouped by outlet. Raises ValidationError for unknown items or options."""
    lines = normalise_cart(cart)
    items = {row["id"]: row for row in conn.execute(
        "SELECT m.id, m.name, m.emoji, m.price_paise, m.prep_minutes, o.id AS outlet_id, o.name AS outlet "
        "FROM menu_item m JOIN outlet o ON o.id = m.outlet_id"
    )}
    option_prices: dict[tuple[int, str], int] = {
        (row["item_id"], row["label"]): row["price_paise"]
        for row in conn.execute("SELECT item_id, label, price_paise FROM item_option")
    }

    by_outlet: dict[int, list[QuoteLine]] = {}
    for line in lines:
        item = items.get(line["item_id"])
        if item is None:
            raise ValidationError(f"Unknown menu item id {line['item_id']}.")
        extra = 0
        for label in line["options"]:
            if (item["id"], label) not in option_prices:
                raise ValidationError(f"'{label}' is not an option for {item['name']}.")
            extra += option_prices[(item["id"], label)]
        unit = item["price_paise"] + extra
        by_outlet.setdefault(item["outlet_id"], []).append(QuoteLine(
            item_id=item["id"], name=item["name"], emoji=item["emoji"], qty=line["qty"],
            options=tuple(line["options"]), unit_price=unit, line_total=unit * line["qty"],
        ))

    outlet_quotes = []
    for outlet_id, outlet_lines in by_outlet.items():
        subtotal = sum(line.line_total for line in outlet_lines)
        tax = tax_on(subtotal)
        fee = seed_data.PICKUP_FEE_RUPEES * 100
        outlet_quotes.append(OutletQuote(
            outlet_id=outlet_id,
            outlet_name=items[outlet_lines[0].item_id]["outlet"],
            lines=tuple(outlet_lines),
            subtotal=subtotal, tax=tax, fee=fee, total=subtotal + tax + fee,
            prep_minutes=max(items[line.item_id]["prep_minutes"] for line in outlet_lines),
        ))
    outlet_quotes.sort(key=lambda q: q.outlet_name)
    return Quote(
        outlets=tuple(outlet_quotes),
        subtotal=sum(q.subtotal for q in outlet_quotes),
        tax=sum(q.tax for q in outlet_quotes),
        fee=sum(q.fee for q in outlet_quotes),
        total=sum(q.total for q in outlet_quotes),
    )


def rupees(paise: int) -> str:
    """₹1,234.50 style; whole rupees drop the decimals."""
    whole, part = divmod(paise, 100)
    return f"₹{whole:,}" if part == 0 else f"₹{whole:,}.{part:02d}"
