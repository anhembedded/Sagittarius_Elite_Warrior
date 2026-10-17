"""Which `python-binance` kline family a `MarketType`'s klines resolve against (`EPIC-027A`).

Its own file, beside the only client that passes it to the SDK, because `HistoricalKlinesType`
is the SDK's: the venue contracts (`support/binance_gateway/contracts/binance_endpoints.py`)
import nothing from `python-binance`, so a run that only resolves a venue's testnet flag
does not import ~0.4 s of SDK (`PRO-014`).
"""

from __future__ import annotations

from binance.enums import HistoricalKlinesType
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType

#: Which `klines_type` `get_historical_klines_generator()` should use for a
#: given `MarketType` (`EPIC-027A`; keyed by venue before that — the venue
#: picks the host via `Client(testnet=...)`, the market picks the klines
#: family, and the two vary independently per call). All three values share
#: one pagination/retry pipeline inside `python-binance`
#: (`_historical_klines_generator` -> `_klines`) — verified by reading the
#: installed library's own source, not assumed.
_KLINES_TYPE: dict[MarketType, HistoricalKlinesType] = {
    MarketType.SPOT: HistoricalKlinesType.SPOT,
    MarketType.FUTURES_USD_M: HistoricalKlinesType.FUTURES,
    MarketType.FUTURES_COIN_M: HistoricalKlinesType.FUTURES_COIN,
}


def klines_type_for(market: MarketType) -> HistoricalKlinesType:
    """Returns which `python-binance` kline family a `MarketType`'s klines
    resolve against. Exchange-info/symbol-catalog calls are unaffected —
    `021C`'s concern, not this one's (see `EPIC-021A` §2.2b)."""
    return _KLINES_TYPE[market]
