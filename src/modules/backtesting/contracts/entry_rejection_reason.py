"""`EPIC-027C` — why an exchange filter refused a simulated entry."""

from enum import Enum


class EntryRejectionReason(str, Enum):
    """@brief The exchange rule an entry failed. A rejected entry opens
    nothing and the run continues (ADR D5); the reason is logged per entry and
    the total rides on `BacktestResult.rejected_entries`."""

    #: The quantity, floored to the step size, is below LOT_SIZE `minQty`.
    BELOW_MIN_QUANTITY = "below_min_quantity"
    #: `quantity * price` is below the symbol's minimum notional.
    BELOW_MIN_NOTIONAL = "below_min_notional"
