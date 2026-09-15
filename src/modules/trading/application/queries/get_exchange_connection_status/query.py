from dataclasses import dataclass


@dataclass(frozen=True)
class GetExchangeConnectionStatusQuery:
    """
    @brief Query to check whether this app can reach and sign requests to
    the trading venue, and what state that account is in (`EPIC-021D`).
    @details No fields — there is exactly one trading venue this epic ever
    checks (`TradingVenue.FUTURES_TESTNET`, ADR §3), so there is nothing
    for a caller to parameterize.
    """
