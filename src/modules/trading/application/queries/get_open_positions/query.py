from dataclasses import dataclass


@dataclass(frozen=True)
class GetOpenPositionsQuery:
    """@brief Query for the account's current open positions (`EPIC-024B`
    §2): the manual order form must read the real position before mapping
    a Long/Short button click to `OrderSide`/`reduce_only`, not guess from
    symbol/side alone.
    @details No fields, same reasoning `GetExchangeConnectionStatusQuery`
    already gives: there is exactly one trading venue this app ever reads
    positions from (`TradingVenue.FUTURES_TESTNET`), and `ITradingClient.
    get_positions()` with no symbol already reads the whole account.
    """
