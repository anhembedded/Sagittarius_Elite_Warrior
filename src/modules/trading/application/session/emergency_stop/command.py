from dataclasses import dataclass


@dataclass(frozen=True)
class EmergencyStopCommand:
    """@brief Command to stop everything, right now (`EPIC-021K`).

    @details No fields — account-wide, like `EnableTradingCommand`/
    `DisableTradingCommand`. Always attempted in full even when trading
    was already off or the account was already flat; each step's own
    result says what it actually found.
    """
