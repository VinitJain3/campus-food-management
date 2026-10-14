"""Order statuses and which of them hold stock (BRD section 7 and 8)."""


class Status:
    SUBMITTED = "Submitted"
    CONFIRMED = "Confirmed"
    PREPARING = "Preparing"
    READY = "Ready for Pickup"
    COLLECTED = "Collected"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"


ALL_STATUSES = (
    Status.SUBMITTED,
    Status.CONFIRMED,
    Status.PREPARING,
    Status.READY,
    Status.COLLECTED,
    Status.REJECTED,
    Status.CANCELLED,
)

# Statuses whose order lines count against a slot's availability.
# Submitted and Confirmed: PDF BC-2. Preparing and Ready: stages of a confirmed
# order (A-02). Collected: units are consumed, not returned (A-01, proposed) -
# remove it from this set if the customer rejects A-01.
COUNTED = frozenset({
    Status.SUBMITTED,
    Status.CONFIRMED,
    Status.PREPARING,
    Status.READY,
    Status.COLLECTED,
})

# No action is allowed once an order reaches one of these (BC-7, BC-11).
TERMINAL = frozenset({Status.COLLECTED, Status.REJECTED, Status.CANCELLED})
