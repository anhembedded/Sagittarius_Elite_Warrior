from dataclasses import dataclass


@dataclass(frozen=True)
class EnableTradingCommand:
    """@brief Command to turn live trading on for this session
    (`EPIC-021G`).
    @details No fields — reconciliation is account-wide (ADR §4), and
    `TradingVenue` has exactly one tradeable venue (ADR §3), so there is
    nothing for a caller to parameterize.
    """
