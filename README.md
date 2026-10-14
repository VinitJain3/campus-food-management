# Campus Food Pre-Order and Pickup Management System

A locally runnable prototype for the IIIT Hackathon challenge. Customers pre-order food from five campus outlets for a pickup slot. The **whole order** is checked against what is left in that slot and reserved at once, or nothing is reserved. Outlet staff then confirm or reject it, prepare it, and hand it over. Rejected and cancelled orders release their stock immediately.

Python 3.10+ · Streamlit · SQLite (standard library) · pytest. No cloud, external APIs or paid services.

**Consulting pitch:** [PITCH.md](PITCH.md) (two slides: problem understanding; solution and engineering decisions).

## Prerequisites

- Python 3.10 or newer (developed and tested with Python 3.13 on Windows 11)
- pip (bundled with Python)
- No database server: SQLite ships with Python

## Run it

```bash
# 1. Create a virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt

# 2. Start the app (creates and seeds campus_food.db on first start)
streamlit run app.py              # opens http://localhost:8501

# 3. Run the automated tests (70 tests, about 10 seconds)
pytest
```

- **Windows "running scripts is disabled" error on activate:** skip activation and call the environment's Python directly: `.\.venv\Scripts\python -m pip install -r requirements.txt`, then `.\.venv\Scripts\python -m streamlit run app.py` and `.\.venv\Scripts\python -m pytest`. Or allow scripts for the current window only: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
- **Reset:** in the app, switch to *Outlet staff*, tick the confirmation box and press *Reset demo data*. This deletes all orders and reloads the challenge data. Deleting `campus_food.db` while the app is stopped does the same.
- **Database location:** set the `CAMPUS_FOOD_DB` environment variable to use a different file.

## Project structure

```
app.py                     Streamlit UI only: sidebar, customer page, staff page
campus_food/
  status.py                Order statuses; which statuses hold stock (COUNTED)
  errors.py                Business errors with user-facing messages
  seed_data.py             Challenge data: outlets, menu, slots, Cold Coffee restriction, commitments
  db.py                    SQLite connection, schema + constraints, seed-once, reset, write transactions
  inventory.py             Menu, slots, availability calculation, whole-order line checks
  orders.py                Submit order, lifecycle transitions, order listing
tests/
  conftest.py              Fresh seeded database per test + helpers
  test_inventory.py        Seed figures, availability, all-or-nothing, concurrent submissions
  test_lifecycle.py        Confirm, reject, cancel, prepare, ready, collect, invalid transitions
  test_persistence.py      Restart, seed-once, reset, database constraints
  test_app_e2e.py          Full workflows through the real Streamlit UI (headless)
```

`app.py` contains no business rules. Removing every check from the UI would leave the system equally correct, because `campus_food/` enforces them all.

## Initial data

| Outlet | Item | Category | Qty per slot | Challenge condition |
|---|---|---|---:|---|
| Coffee | Cold Coffee | Beverages | 18 | Unavailable for all slots on 4 Aug 2026 |
| Fast Food | Veg Sandwich | Snacks | 20 | 8 committed, 4 Aug 2026 13:00–13:30 |
| Main Meal | Paneer Rice Bowl | Meals | 12 | 5 committed, 4 Aug 2026 12:30–13:00 |
| Pure Veg | Masala Dosa | South Indian | 15 | All available |
| Healthy Food | Fruit Bowl | Healthy Meals | 10 | 4 committed, 4 Aug 2026 13:00–13:30 |

Slots are 12:30–13:00 and 13:00–13:30 on **4 Aug 2026** and **5 Aug 2026**. 5 Aug shows that the date-specific conditions do not carry over.

## How the core rules are enforced

| Rule | Where | How |
|---|---|---|
| Availability per item per slot | `inventory.get_availability` | Calculated from orders every time: quantity per slot − units in orders whose status is in `COUNTED`; 0 if restricted. No stored counter, so stock can't be reserved or released twice |
| Whole order or nothing | `orders.submit_order` → `inventory.check_lines` | Every line is checked. If any line is short, nothing is written and every failing line is listed |
| No overbooking under concurrency | `db.write_transaction` | `BEGIN IMMEDIATE` takes SQLite's write lock before the recheck, so two submissions can't claim the same units. Tested with 12 simultaneous threads |
| Reserve on submit | `orders.submit_order` | Inserting the order (Submitted) and its lines *is* the reservation |
| Release on reject or cancel | `status.COUNTED` | Rejected and Cancelled are outside `COUNTED`, so the lines stop counting the moment the status changes |
| Allowed status changes | `orders.ACTIONS` + `orders.transition` | One table of action → from, to, role. Anything else is refused with a specific message; the update is conditional on the expected current status |
| No cancel after preparation; collect once | `orders.transition` | Cancel needs Confirmed; collect needs Ready for Pickup. Repeats are refused |

Order lifecycle: **Submitted → Confirmed → Preparing → Ready for Pickup → Collected**, plus **Submitted → Rejected** (staff, reason required) and **Confirmed → Cancelled** (customer, before preparation). Collected, Rejected and Cancelled are final.

## Demo script

The full presentation runbook, with exact steps, expected results and talking points, is in [DEMO.md](DEMO.md). Short version:

1. **Customer** "Asha": slot *Tue 4 Aug 2026, 13:00–13:30*. Fruit Bowl shows *6 of 10 left*, Veg Sandwich *12 of 20*, Cold Coffee *Unavailable*.
2. Order 2 Masala Dosa + 1 Fruit Bowl and submit. You get order #4, *Submitted*; Fruit Bowl drops to 5.
3. **Failure:** order 6 Fruit Bowl + 13 Veg Sandwich. The order is refused, naming Veg Sandwich (13 requested, 12 left), and nothing is reserved.
4. **Restriction:** 1 Cold Coffee on 4 Aug is refused. The same order on 5 Aug is accepted.
5. **Staff:** confirm #4 → Start preparing → Mark ready → Mark collected. Collecting #4 again from *Collect by order number* is refused.
6. **Release:** a customer orders all remaining Fruit Bowls. Staff reject it with a reason, and the *Availability by slot* tab shows them back.
7. **Cancel rule:** a customer can cancel a Confirmed order (stock returns), but the Cancel button disappears once it's Preparing; the core refuses it anyway.
8. **Concurrency:** two browser tabs order the last Fruit Bowls at the same time. Exactly one succeeds.

## Assumptions (proposed, not yet approved by the customer)

| ID | Assumption |
|---|---|
| A-01 | Collected units stay used and are never returned to the slot. A literal reading of the PDF could free them; that would let a slot sell more than it makes. To reverse it, remove `COLLECTED` from `status.COUNTED` |
| A-02 | Preparing and Ready for Pickup count against availability as stages of a confirmed order |
| A-03 | The challenge's commitments are stored as Confirmed orders from customer "Pre-existing (seed)", so they behave like every other order |
| A-04 | Pickup slots are 12:30–13:00 and 13:00–13:30 on 4 and 5 Aug 2026 |
| A-05 | Past dates and order cut-off times are not enforced, so the 4 Aug 2026 data can be demonstrated |
| A-06 | Outlet staff confirm or reject by hand; nothing is automatic and nothing times out |
| A-07 | Only the customer cancels, only a Confirmed order, and only before preparation. A Submitted order can't be withdrawn |
| A-08 | Preparation starts when staff press *Start preparing* |
| A-10 | No authentication: a role switch and a typed customer name |
| OA-01 | **Five outlets, one item each.** An order may contain items from several outlets and is handled as one unit (confirmed or rejected as a whole), which keeps the all-or-nothing rule. Staff can filter the queue by outlet |
| DA-04 | The PDF gives no reason for Cold Coffee's unavailability; the seed uses "operational restriction" |
| DA-05 | A submission that can't get the database lock within 5 seconds fails cleanly and nothing is saved |

## Scope (prioritized)

We built the rules that protect stock and the order lifecycle first, tested them, and only then built the screens.

| Priority | Scope | Status |
|---|---|---|
| **Must:** challenge rules | Exact challenge data; availability per item per slot; whole-order validation; atomic reservation; safe concurrent submissions; confirm or reject; stages through to Collected; customer cancel before preparation; release on reject and cancel; invalid transitions and repeat collection refused | Built and tested |
| **Must:** demonstrability | Customer and staff screens; status view; clear failure messages; local persistence across restarts; reset to challenge data | Built and tested |
| **Should** | Staff filters (slot, status, outlet); availability grid; collect by order number; rejection reason; 5 outlets | Built |
| **Could** (bonus candidates) | Slot suggestions when an order doesn't fit; "ready" notifications; demand view | Not built |
| **Won't** (this prototype) | See *Excluded* below | Excluded |

**Excluded:**
- Authentication.
- Prices and payment.
- Notifications.
- Screens for editing slots, menu or item restrictions.
- Past-slot cut-offs and no-show handling.
- Editing a submitted order (the PDF requires a new pre-order instead).
- Partial fulfilment, splitting across slots and substitutions (the PDF says these are not required).

## Testing and validation

`pytest` runs 70 tests in about 7 seconds. Each test gets a fresh seeded database.

| File | Tests | What it proves |
|---|---:|---|
| `test_inventory.py` | 26 | Exact challenge figures per slot; 5 Aug unaffected by 4 Aug conditions; a successful order reserves every line; one short line refuses the whole order and reserves nothing; every failing line is reported; Cold Coffee refused on 4 Aug and accepted on 5 Aug; sold out; slots independent; invalid input; **2 and 12 simultaneous orders never overbook** |
| `test_lifecycle.py` | 31 | Full lifecycle; confirming doesn't change stock; **rejection and cancellation release stock** (same slot only); rejection reason required; **no cancel once Preparing or Ready**; **collect once only**, even with two staff at once; closed orders can't change; steps can't be skipped; role and ownership checks |
| `test_persistence.py` | 9 | Data survives restart; seed loads once; reset restores the challenge data; database constraints reject bad rows |
| `test_app_e2e.py` | 4 | Full workflows through the real Streamlit UI (headless): order → confirm → prepare → ready → collect → repeat collect refused; all-or-nothing failure; reject with reason and customer cancel; reset |

We checked that the concurrency tests can fail: with the database write lock removed, both race tests failed with overbooking. With the lock restored, they pass. We also ran the app with `streamlit run app.py` and checked its availability grid against the challenge figures.

## Trade-offs and known limitations

- **No login.** Anyone can act as any customer or as staff. Customer cancellation only checks the typed name.
- **Staff screens refresh on interaction or the Refresh button.** There is no live push of new orders.
- **Writes are serialized** by SQLite's single writer lock. This is correct and fast enough for one campus; it would need a server database at larger scale.
- **One order covers several outlets** and is confirmed as a whole (OA-01). Per-outlet confirmation would need the order split into per-outlet parts.
- `index.html` is a static mock-up from the initial commit. The app doesn't use it.

## Next steps

Customer approval of the assumptions above · slot suggestions when an order doesn't fit (the whole order in another slot, never splitting it) · "ready for pickup" notifications · per-outlet confirmation · order cut-off times · authentication.
