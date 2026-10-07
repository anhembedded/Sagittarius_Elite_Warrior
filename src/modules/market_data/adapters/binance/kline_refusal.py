"""What Binance's refusals of a kline request mean, in words (`BUG-172`).

A testnet is a smaller exchange than the mainnet: Futures has no `1s` klines and
each testnet lists fewer symbols. Binance answers those two requests with an API
error that retrying cannot change, and `PythonBinanceClient` turns exactly them
into `ExchangeRefusedKlinesError`; any other answer is left as the SDK raised it.
"""

from __future__ import annotations

from typing import NoReturn

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRefusedKlinesError,
)

#: What Binance answers when it will never serve a kline request: an interval
#: the market has none of (Futures has no `1s`), and a symbol the exchange does
#: not list (each testnet lists fewer than the mainnet).
_INVALID_INTERVAL = -1120
_INVALID_SYMBOL = -1121

#: A market as a person says it, in the sentences below.
_MARKET_WORDS: dict[MarketType, str] = {
    MarketType.SPOT: "Spot",
    MarketType.FUTURES_USD_M: "USDⓈ-M Futures",
    MarketType.FUTURES_COIN_M: "COIN-M Futures",
}


def reraise_as_refusal(
    exc: BinanceAPIException, market: MarketType, symbol: str, interval: str
) -> NoReturn:
    """Raises the permanent refusal Binance's answer means, in words, `from exc`;
    any other answer is raised again as it is — not this function's to translate."""
    if exc.code == _INVALID_INTERVAL:
        raise ExchangeRefusedKlinesError(
            f"This exchange has no {interval} candles for its "
            f"{_MARKET_WORDS[market]} market."
        ) from exc
    if exc.code == _INVALID_SYMBOL:
        raise ExchangeRefusedKlinesError(
            f"This exchange does not list {symbol} on its "
            f"{_MARKET_WORDS[market]} market."
        ) from exc
    raise exc
