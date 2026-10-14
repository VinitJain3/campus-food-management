# Demo Runbook

A rehearsed path through the app for the final presentation, about 10 minutes. Every order number and stock figure below was checked by running this exact sequence against a freshly reset database. **Follow the steps in order, starting from a reset.** Each step changes the numbers for the next one.

## Before you present (2 minutes)

1. Start the app: `.\.venv\Scripts\python -m streamlit run app.py`. It opens http://localhost:8501.
2. Open **two browser windows** side by side, both on http://localhost:8501. Each window keeps its own role.
   - **Window C (customer):** sidebar → *I am* = **Customer**.
   - **Window S (staff):** sidebar → *I am* = **Outlet staff**.
3. In Window S: tick *Delete all orders and reload the challenge data* → **Reset demo data**.
4. Have a terminal open in the project folder for the test run in scenario 7.

The staff queue always shows orders **#1–#3 (Confirmed, "Pre-existing (seed)")**. These are the challenge's commitments (8 Veg Sandwich, 5 Paneer Rice Bowl, 4 Fruit Bowl on 4 Aug), stored as orders. Your first new order is **#4**.

## What the evaluators asked to see, and where it is

| Required in the demo | Scenario |
|---|---|
| Successful end-to-end scenario | 1 |
| Conflict, invalid or failure scenario | 2, 3, 4, 5, 6 |
| Business rules | All: each step says which rule it shows |
| Design decisions | Talking points in 2, 4 and 6 |
| Testing performed | 7 |
| Assumptions, trade-offs, limitations, next steps | [PITCH.md](PITCH.md), slide 2 |

---

## Scenario 1: Happy path, order to collection (3 min)

*Shows: the full lifecycle (BC-6, BC-10, BC-11); reservation on submit (BC-2).*

| # | Window | Do | You should see |
|---|---|---|---|
| 1.1 | C | Name **Asha**. Pickup slot **Tue 4 Aug 2026, 13:00-13:30** | Veg Sandwich *12 of 20 left* · Fruit Bowl *6 of 10* · Masala Dosa *15 of 15* · Paneer Rice Bowl *12 of 12* · Cold Coffee *Unavailable: operational restriction* |
| 1.2 | C | Masala Dosa **2**, Fruit Bowl **2** → **Submit pre-order** | *Order #4 submitted … waiting for outlet confirmation.* Fruit Bowl now **4**, Masala Dosa **13**. Cart clears. *My orders*: #4 **Submitted** |
| 1.3 | S | **Order queue** → #4 under *Submitted* → **Confirm** | *Order #4 confirmed* |
| 1.4 | S | #4 → **Start preparing** → **Mark ready for pickup** | #4 moves to *Preparing*, then *Ready for Pickup* |
| 1.5 | C | Click anywhere (or switch the slot and back) to refresh | #4 shows **Ready for Pickup**, with no Cancel button: *Preparation has started…* |
| 1.6 | S | #4 → **Mark collected** | #4 **Collected** |
| 1.7 | S | **Collect by order number** → enter **4** → **Mark collected** | Refused: ***Order #4 has already been collected.*** |

**Say:** "Stock was reserved the moment Asha submitted, before staff even saw the order. Confirming and preparing don't touch stock. Collection happens exactly once."

---

## Scenario 2: All-or-nothing, the conflict case (1.5 min)

*Shows: BC-3, BC-4, BC-12. A failing order reserves nothing.*

| # | Window | Do | You should see |
|---|---|---|---|
| 2.1 | C | Name **Ben**. Same slot (4 Aug, 13:00). Fruit Bowl **4**, Veg Sandwich **13** → Submit | Refused: *Order not placed and nothing was reserved … Veg Sandwich: requested 13, only 12 left.* The quantities stay in the form |
| 2.2 | C | Point at the menu | Fruit Bowl is **still 4**: the valid line was not reserved either |
| 2.3 | C | Change Veg Sandwich to **12** → Submit | *Order #5 submitted.* Fruit Bowl and Veg Sandwich both show **Sold out** |

**Say:** "Every line is checked inside one database transaction. If any line is short, nothing is written. There's no partial order and no substitution, which is what the challenge says."

---

## Scenario 3: Temporary unavailability is date-specific (1 min)

*Shows: BC-5; the challenge data is applied only to its stated date.*

| # | Window | Do | You should see |
|---|---|---|---|
| 3.1 | C | Name **Chitra**. Slot **Tue 4 Aug 2026, 12:30-13:00**. Cold Coffee **1** → Submit | Refused: *Cold Coffee: temporarily unavailable (operational restriction).* |
| 3.2 | C | Slot **Wed 5 Aug 2026, 12:30-13:00**. Cold Coffee **1** → Submit | *Order #6 submitted.* Cold Coffee **17 of 18 left** |

**Say:** "The PDF made Cold Coffee unavailable on 4 August only, so 5 August is unaffected. The commitments work the same way: on 5 August every item starts at full quantity."

---

## Scenario 4: Rejection releases stock (1.5 min)

*Shows: BC-7. Rejected stock goes back to the same slot immediately.*

| # | Window | Do | You should see |
|---|---|---|---|
| 4.1 | C | (Chitra) Slot **4 Aug, 13:00-13:30**. Fruit Bowl **1** → Submit | Refused: *Fruit Bowl: sold out for this slot* (Ben's #5 holds the last 4) |
| 4.2 | S | #5 (Ben) → **Reject** with the reason box empty | Refused: *Give a reason when rejecting an order.* |
| 4.3 | S | Reason *Fast Food is short of bread* → **Reject** | *Order #5 rejected. Its items are available again.* |
| 4.4 | S | **Availability by slot** tab | 4 Aug 13:00: Fruit Bowl **4 / 10**, Veg Sandwich **12 / 20** |
| 4.5 | C | Chitra: Fruit Bowl **1** → Submit | *Order #7 submitted* |
| 4.6 | C | (Optional) Name **Ben** | #5 **Rejected**, with the reason shown |

**Say:** "We never store a stock counter. Availability is calculated from the orders that still hold stock. Rejecting just changes the status, so the stock comes back automatically and can't be released twice."

---

## Scenario 5: Cancellation rules (1.5 min)

*Shows: BC-8, BC-9.*

| # | Window | Do | You should see |
|---|---|---|---|
| 5.1 | C | (Chitra) *My orders*: #7 is **Submitted** | No Cancel button: *Waiting for the outlet to confirm* (only Confirmed orders can be cancelled, A-07) |
| 5.2 | S | #7 → **Confirm** | #7 Confirmed |
| 5.3 | C | Refresh → #7 → **Cancel order** | *Order #7 cancelled. Its items are available again.* Fruit Bowl back to **4** |
| 5.4 | C | Chitra: Masala Dosa **1** → Submit | *Order #8 submitted* |
| 5.5 | S | #8 → **Confirm** → **Start preparing** | #8 Preparing |
| 5.6 | C | Refresh → #8 | **No Cancel button**: *Preparation has started, so this order can no longer be cancelled.* |

**Say:** "The screen hides the button, but that isn't the protection. The rule lives in the core: even a direct call is refused with *Order #8 is Preparing: preparation has started*. Our tests check this without the UI."

---

## Scenario 6: Two customers, last units (1 min)

*Shows: BC-3 under concurrency.*

| # | Window | Do | You should see |
|---|---|---|---|
| 6.1 | — | Open a third window as Customer. Window C: name **Dev**; new window: name **Esha**. Both on slot 4 Aug 13:00 | Both show Fruit Bowl **4 of 10 left** |
| 6.2 | Both | Both enter Fruit Bowl **4**, then click **Submit** in both windows as close together as you can | One gets *Order #9 submitted*; the other is refused: *Fruit Bowl: sold out for this slot* |

**Say (honestly):** "Clicking by hand rarely makes the two requests overlap exactly, so the real proof is the automated test. Twelve threads order the last six units at the same instant, and exactly six succeed. When we removed the database write lock, that test failed with overbooking. That's how we know the test works."

---

## Scenario 7: Testing (1 min)

In the terminal:

```powershell
.\.venv\Scripts\python -m pytest -v
```

**Expected:** `70 passed`.

Point to these test names:
- `test_ac04_one_short_line_fails_the_whole_order_and_reserves_nothing`
- `test_twelve_simultaneous_orders_never_exceed_capacity`
- `test_ac12_cancel_refused_once_preparation_has_started`
- `test_ac14_order_cannot_be_collected_twice`
- `test_customer_and_staff_end_to_end` (drives the real UI headlessly)

**Optional (persistence):** stop the app (Ctrl+C), start it again and refresh. Every order is still there (SQLite file `campus_food.db`).

---

## If an evaluator gives you their own scenario

| They ask | Do this |
|---|---|
| "Order more than is left" | Any item, quantity above the *left* figure → refused, naming the item, requested quantity and what's left |
| "What if one item is unavailable?" | Add Cold Coffee to any 4 Aug order → the whole order is refused |
| "Cancel after cooking started" | Scenario 5.5–5.6 |
| "Collect twice" | Scenario 1.7 |
| "Reject a confirmed order" | Not offered: only Submitted orders can be rejected. A Confirmed order can only be cancelled by the customer, or moved forward |
| "Change an order" | Not possible by design (BC-7): reject or cancel, then place a new pre-order |
| "Does a collected order give stock back?" | No: collected units stay used (assumption A-01, awaiting the customer's decision; a one-line change in `status.py`) |
| "Another outlet's view" | Window S → *Outlet* = e.g. **Healthy Food**: the queue shows only orders containing its items |
| "Start again" | Window S → tick the box → **Reset demo data** |

## Suggested split for a team

The PDF says each member must explain their contribution, one business rule, one part of the solution, one assumption or trade-off, and how their work was validated.

| Presenter | Scenarios | Rule to own | Code to own |
|---|---|---|---|
| Member 1 | Problem (pitch slide 1), scenario 1 | Reserve on submit; lifecycle | `orders.transition`, `ACTIONS` |
| Member 2 | Scenarios 2, 3, 6 | All-or-nothing; no overbooking | `orders.submit_order`, `db.write_transaction` |
| Member 3 | Scenarios 4, 5 | Release on reject or cancel; no cancel after preparation | `inventory.get_availability`, `status.COUNTED` |
| Member 4 | Scenario 7, pitch slide 2 | How we validated | `tests/`, README |

## If something goes wrong live

- **Unexpected numbers:** you skipped or repeated a step. Reset (Window S) and restart from scenario 1, or just continue: every rule still holds and only the numbers differ.
- **A window looks stale:** click **Refresh** (staff) or change the slot and back (customer).
- **The app won't start on 8501:** another copy is running. Use the URL Streamlit prints (for example 8502), or close the other terminal.
