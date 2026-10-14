"""Order statuses and which of them hold stock (BRD sections 7 and 8).

Customer-facing names, mapped to the challenge's vocabulary:
Placed = submitted pre-order, Accepted = confirmed order, Delivered = collected
(handed over at the counter). Completed closes a delivered order (cash
settled for Cash on Delivery).
"""


class Status:
    PLACED = "Placed"
    ACCEPTED = "Accepted"
    PREPARING = "Preparing"
    READY = "Ready"
    DELIVERED = "Delivered"
    COMPLETED = "Completed"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"

    # The challenge PDF's names for the same statuses.
    SUBMITTED = PLACED
    CONFIRMED = ACCEPTED
    COLLECTED = DELIVERED


ALL_STATUSES = (
    Status.PLACED,
    Status.ACCEPTED,
    Status.PREPARING,
    Status.READY,
    Status.DELIVERED,
    Status.COMPLETED,
    Status.REJECTED,
    Status.CANCELLED,
)

# The forward path shown on the order timeline.
TIMELINE = (
    Status.PLACED,
    Status.ACCEPTED,
    Status.PREPARING,
    Status.READY,
    Status.DELIVERED,
    Status.COMPLETED,
)

# Statuses whose order lines count against a slot's availability.
# Placed and Accepted: PDF BC-2. Preparing and Ready: stages of an accepted
# order (A-02). Delivered and Completed: units are consumed, not returned
# (A-01, proposed) - remove them from this set if the customer rejects A-01.
COUNTED = frozenset({
    Status.PLACED,
    Status.ACCEPTED,
    Status.PREPARING,
    Status.READY,
    Status.DELIVERED,
    Status.COMPLETED,
})

# No action is allowed once an order reaches one of these (BC-7, BC-11).
TERMINAL = frozenset({Status.COMPLETED, Status.REJECTED, Status.CANCELLED})

# Orders still in progress, from the customer's point of view.
ACTIVE = frozenset({Status.PLACED, Status.ACCEPTED, Status.PREPARING, Status.READY})
