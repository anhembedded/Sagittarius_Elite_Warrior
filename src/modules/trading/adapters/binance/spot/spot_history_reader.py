"""`EPIC-028E` — `IAccountHistoryReader` for Spot.

@details `GET /api/v3/allOrders` and `GET /api/v3/myTrades` both need a
symbol, accept at most twenty-four hours between `startTime` and `endTime`,
and return at most 1 000 rows; `fetch_span` turns a seven-day request into
seven or more requests within those limits (weight 20 each; the thirty-day
`MAX_HISTORY_LOOKBACK` caps a read at 600 weight per symbol).

`active_symbols` is the USDT pair of every held asset other than USDT itself
(ADR D9: USDT-quoted only) that the exchange actually lists, plus every
symbol with an open order. The listing check matters: a testnet account holds
assets with no USDT pair, and asking `myTrades` for one is an error, not an
empty answer. `ListedSymbols` answers it without downloading the catalog once
per unlisted asset.

Payload shapes and limits follow Binance's documented Spot API, with the
same live-call disclosure as `spot_account_reader.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_reads import (
    history_read_failures,
    require_credentials,
    span_ms,
    utc_now,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_window import (
    HistoryWindowRules,
    fetch_span,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.listed_symbols import (
    ListedSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_payload_mapper import (
    map_spot_history_order,
    map_spot_trade,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionClient,
    ISpotSessionFactory,
)

_QUOTE_ASSET = "USDT"
_ROW_LIMIT = 1000
_RULES = HistoryWindowRules(max_span_ms=24 * 60 * 60 * 1000, limit=_ROW_LIMIT)
_VENUE = "Spot"


def _held_assets(account: dict[str, Any]) -> set[str]:
    """Every asset with a positive balance, the quote asset excluded."""
    held: set[str] = set()
    for balance in account.get("balances", []):
        try:
            total = Decimal(str(balance.get("free", "0"))) + Decimal(
                str(balance.get("locked", "0"))
            )
        except InvalidOperation:
            continue
        if total > 0 and balance.get("asset") != _QUOTE_ASSET:
            held.add(balance["asset"])
    return held


class SpotHistoryReader(IAccountHistoryReader):
    """Reads one Spot account's orders and fills, symbol by symbol."""

    def __init__(
        self,
        session_factory: ISpotSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        listed_symbols: ListedSymbols,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._listed_symbols = listed_symbols
        self._clock = clock

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        start, end = span_ms(since, self._clock())
        with history_read_failures(f"{_VENUE} order history could not be read"):
            client = self._client()
            rows = fetch_span(
                lambda s, e: client.get_all_orders(
                    symbol=symbol, startTime=s, endTime=e, limit=_ROW_LIMIT
                ),
                start,
                end,
                _RULES,
            )
        return tuple(map_spot_history_order(row) for row in rows)

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        start, end = span_ms(since, self._clock())
        with history_read_failures(f"{_VENUE} trade history could not be read"):
            client = self._client()
            rows = fetch_span(
                lambda s, e: client.get_my_trades(
                    symbol=symbol, startTime=s, endTime=e, limit=_ROW_LIMIT
                ),
                start,
                end,
                _RULES,
            )
        return tuple(map_spot_trade(row) for row in rows)

    def active_symbols(self) -> tuple[str, ...]:
        with history_read_failures(f"{_VENUE} active symbols could not be read"):
            client = self._client()
            account: dict[str, Any] = client.get_account()
            open_orders: list[dict[str, Any]] = client.get_open_orders()
            listed = self._listed_symbols.among(
                f"{asset}{_QUOTE_ASSET}" for asset in _held_assets(account)
            )
        return tuple(sorted(listed | {row["symbol"] for row in open_orders}))

    def _client(self) -> ISpotSessionClient:
        return self._session_factory.create_account_client(
            require_credentials(self._credentials_provider, _VENUE)
        )
