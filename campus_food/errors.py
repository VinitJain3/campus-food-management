"""Business errors. Each carries a `message` that is safe to show to end users."""

from dataclasses import dataclass


class BusinessError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(BusinessError):
    """Bad input: missing name, empty cart, invalid quantity, unknown item (ERR-05)."""


class NotFound(BusinessError):
    """Unknown order or pickup slot (ERR-13)."""


class InvalidTransition(BusinessError):
    """A status change that the lifecycle or the actor's role does not allow (ERR-07 to ERR-11)."""


class PersistenceError(BusinessError):
    """The database could not complete the change; nothing was saved (ERR-12)."""


@dataclass(frozen=True)
class LineFailure:
    """One order line that cannot be fulfilled for the chosen slot."""

    item_name: str
    requested: int
    available: int
    restriction: str | None = None  # human-readable reason when the item is restricted

    def describe(self) -> str:
        if self.restriction:
            return f"{self.item_name}: temporarily unavailable ({self.restriction})."
        if self.available == 0:
            return f"{self.item_name}: sold out for this slot (requested {self.requested})."
        return f"{self.item_name}: requested {self.requested}, only {self.available} left."


class AvailabilityError(BusinessError):
    """The whole order was refused because at least one line is short (ERR-01 to ERR-04, ERR-06)."""

    def __init__(self, failures: list[LineFailure], slot_label: str):
        self.failures = failures
        lines = "\n".join(f"- {failure.describe()}" for failure in failures)
        super().__init__(
            f"Order not placed and nothing was reserved for {slot_label}. "
            f"The complete order must be available:\n{lines}"
        )
