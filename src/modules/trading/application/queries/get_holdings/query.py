from dataclasses import dataclass


@dataclass(frozen=True)
class GetHoldingsQuery:
    """@brief Query for the account's current Spot holdings (`EPIC-027O`).

    @details No fields, same reasoning `GetOpenPositionsQuery` already gives:
    `ITradingAccountReader.check_connection()` with no symbol already reads
    the whole account's balances.
    """
