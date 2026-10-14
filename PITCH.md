# Consulting Pitch: Campus Food Pre-Order and Pickup

Two slides, as required by the challenge. Details and evidence are in the [README](README.md).

---

## Slide 1: Problem understanding

**The problem.** Campus outlets take orders at the counter and by message, so stock is promised without being checked. Several orders chase the same last units, cancelled orders keep holding food, and nobody can see where an order stands. The root cause is that there is **no single source of truth for what is left, per item, per pickup slot**, and **no controlled order lifecycle**.

**Stakeholders**

| Persona | Needs |
|---|---|
| Customer (student or staff member) | Know what's available for a slot, order once, see status, cancel if plans change |
| Outlet staff (5 outlets: Coffee, Fast Food, Main Meal, Pure Veg, Healthy Food) | One queue to confirm or reject, prepare, hand over; never overcommit stock |
| Later: outlet manager, campus admin | Menu and slot setup, demand reports (out of scope for 90 minutes) |

**Workflows we prioritized**

1. Customer: choose slot → see live availability → submit a whole order → track status → cancel before preparation.
2. Staff: confirm or reject (with a reason) → Preparing → Ready for Pickup → Collected (once only).

**Business rules discovered**

- Stock is limited **per item, per slot**. A submitted order reserves its quantities immediately.
- **All or nothing:** if any item is short, the whole order is refused and the reason is shown. There is no partial fulfilment, splitting or substitution.
- Every order passes confirmation. **Rejection and pre-preparation cancellation release all stock** to the same slot.
- **No customer cancellation after preparation starts. An order is collected exactly once.**
- The challenge data is used exactly: the commitments and the Cold Coffee restriction apply **only on 4 Aug 2026**.

**Key assumptions (pending customer approval)**

- Collected units stay used and are not returned to the slot.
- The challenge's commitments are modelled as pre-existing confirmed orders.
- One order may span outlets and is confirmed as a whole.
- No login.
- No past-date cut-off, so the 4 Aug data can be demonstrated.

**Scope for 90 minutes.** One reliable end-to-end lifecycle with every rule enforced and tested. Prices, payment, authentication and notifications are excluded.

---

## Slide 2: Solution and engineering decisions

**Approach.** Python + Streamlit + SQLite, in three layers:
- **UI** (`app.py`): no business rules.
- **Business rules** (`campus_food/`): testable without the UI.
- **Persistence** (`db.py`): one local file, standard library only.

**Design decisions**

| Decision | Why |
|---|---|
| Availability is **calculated from orders**, never a stored counter | Reserving = inserting an order; releasing = a status change. Stock can't drift or be released twice |
| Submission runs inside one **write-locked transaction** (`BEGIN IMMEDIATE`) | Two customers can't buy the same last units; a failed order writes nothing |
| One **transition table** drives every status change, with a conditional update | Invalid moves, cancel-after-preparation and double collection are refused with a clear message, even when two staff click at once |
| Database constraints (CHECK, UNIQUE, foreign keys) | A second line of defence against bad data |

**Trade-offs**

- No login: faster to build, and the role switch is clearly labelled.
- Staff refresh manually: no live push.
- SQLite runs writes one at a time: right for one campus, not for scale.
- Whole-order confirmation across outlets: simple and consistent, but less flexible than per-outlet confirmation.

**Testing and validation.** 70 automated tests (pytest), mapped to the BRD acceptance criteria:
- Exact seed figures.
- All-or-nothing submission.
- **12 simultaneous orders for 6 units: exactly 6 succeed.**
- Rejection and cancellation release stock.
- Collect once only.
- Every invalid transition.
- Restart and reset.
- Four full workflows driven through the real UI (Streamlit AppTest).

We also checked that the concurrency tests catch overbooking: with the lock removed, they fail.

**Known limitations**

- No authentication; customer identity is a typed name.
- No order cut-off times or no-show handling.
- No price or payment.
- Restricting an item is done in seed data, not in a screen.

**What we would improve next**

1. Get the customer's sign-off on the assumptions.
2. **Smart slot suggestions:** when an order doesn't fit, show slots where the *whole* order fits.
3. "Ready for pickup" notifications.
4. Per-outlet confirmation.
5. Order cut-off times and authentication.
