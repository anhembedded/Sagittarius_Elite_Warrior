"""`EPIC-028E` — `IAccountHistoryReader` for USD-M Futures.

@details `GET /fapi/v1/allOrders` and `GET /fapi/v1/userTrades` both need a
symbol, accept at most seven days between `startTime` and `endTime`, and
return at most 1 000 rows; `fetch_span` turns any requested span into
requests within those limits. Binance keeps Futures order history for 90
days and trade history for six months, both beyond `MAX_HISTORY_LOOKBACK`.

`active_symbols` is every symbol with an open position or an open order —
`positionRisk` and `openOrders` without a symbol, the same two reads
`EnableTradingCommandHandler` reconciles against.

Payload shapes and limits follow Binance's documented USD-M API; they were
not re-verified against a live call (egress to `*.binance.*` is blocked in
this sandbox), the same disclosure as `futures_account_reader.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_payload_mapper import (
    map_futures_history_order,
    map_futures_trade,
)
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)

_ROW_LIMIT = 1000
_RULES = HistoryWindowRules(max_span_ms=7 * 24 * 60 * 60 * 1000, limit=_ROW_LIMIT)
_VENUE = "Futures"


class FuturesHistoryReader(IAccountHistoryReader):
    """Reads one Futures account's orders and fills, symbol by symbol."""

    def __init__(
        self,
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._clock = clock

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        start, end = span_ms(since, self._clock())
        with history_read_failures(f"{_VENUE} order history could not be read"):
            client = self._client()
            rows = fetch_span(
                lambda s, e: client.futures_get_all_orders(
                    symbol=symbol, startTime=s, endTime=e, limit=_ROW_LIMIT
                ),
                start,
                end,
                _RULES,
            )
        return tuple(map_futures_history_order(row) for row in rows)

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        start, end = span_ms(since, self._clock())
        with history_read_failures(f"{_VENUE} trade history could not be read"):
            client = self._client()
            rows = fetch_span(
                lambda s, e: client.futures_account_trades(
                    symbol=symbol, startTime=s, endTime=e, limit=_ROW_LIMIT
                ),
                start,
                end,
                _RULES,
            )
        return tuple(map_futures_trade(row) for row in rows)

    def active_symbols(self) -> tuple[str, ...]:
        with history_read_failures(f"{_VENUE} active symbols could not be read"):
            client = self._client()
            positions: list[dict[str, Any]] = client.futures_position_information()
            open_orders: list[dict[str, Any]] = client.futures_get_open_orders()
        held = {
            row["symbol"]
            for row in positions
            if Decimal(str(row.get("positionAmt", "0"))) != 0
        }
        return tuple(sorted(held | {row["symbol"] for row in open_orders}))

    def _client(self) -> ITradingSessionClient:
        return self._session_factory.create_trading_client(
            require_credentials(self._credentials_provider, _VENUE)
        )
