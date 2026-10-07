"""`EPIC-028E` — `IAccountHistoryReader` for USD-M Futures.

@details `GET /fapi/v1/allOrders` and `GET /fapi/v1/userTrades` both need a
symbol, accept at most seven days between `startTime` and `endTime`, refuse a
`startTime` older than seven days (-4181, `BUG-173`), and
return at most 1 000 rows; `fetch_span` turns any requested span into
requests within those limits. Binance keeps Futures order history for 90
days and trade history for six months, both beyond `MAX_HISTORY_LOOKBACK`.

`active_symbols` is every symbol with an open position or an open order —
`positionRisk` and `openOrders` without a symbol, the same two reads
`EnsureSessionReadyCommandHandler` reconciles against — plus every symbol with
income since `since` (`GET /fapi/v1/income`: a fill books a commission, and
a closed round trip a realized PnL even when its fee is zero), so a round
trip already closed inside the window is found
(`EPIC-028Q`, the PR #300 epic review). What income cannot show, a pair whose
orders were all cancelled unfilled, is in `known_gaps()`, with Binance's
3-day purge of such orders from `allOrders`.

Payload shapes and limits follow Binance's documented USD-M API; they were
not re-verified against a live call (egress to `*.binance.*` is blocked in
this sandbox), the same disclosure as `futures_account_reader.py`.

`EPIC-028R` — order history also lists conditional orders
(`GET /fapi/v1/allAlgoOrders`: seven-day spans, 100 rows), and
`active_symbols` counts open ones (`openAlgoOrders`). A triggered algo order
shows no fill of its own; its fill is on the regular order it placed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_algo_order_mapper import (
    map_futures_algo_history_order,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveReason,
    ActiveSymbol,
    active_symbols_from,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_gaps import (
    HistoryGaps,
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
_SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
#: `BUG-173`: a `startTime` older than seven days at the exchange is refused
#: (-4181), so the oldest start asked for keeps five minutes under it.
_MAX_START_AGE_MS = _SEVEN_DAYS_MS - 5 * 60 * 1000
_RULES = HistoryWindowRules(
    max_span_ms=_SEVEN_DAYS_MS, limit=_ROW_LIMIT, max_age_ms=_MAX_START_AGE_MS
)
#: `allAlgoOrders` answers at most 100 rows per request.
_ALGO_RULES = HistoryWindowRules(
    max_span_ms=_SEVEN_DAYS_MS, limit=100, max_age_ms=_MAX_START_AGE_MS
)
_VENUE = "Futures"
_GAPS = HistoryGaps(
    order_history=(
        (
            "Binance keeps a Futures order that was cancelled or expired without "
            "a fill for 3 days only; older ones are not listed."
        ),
    ),
    every_symbol=(
        (
            "A pair whose orders were all cancelled without a fill, with nothing "
            "open, is not found when reading every pair; choose the pair to see it."
        ),
    ),
)


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
            algo_rows = fetch_span(
                lambda s, e: client.futures_get_all_algo_orders(
                    symbol=symbol, startTime=s, endTime=e, limit=_ALGO_RULES.limit
                ),
                start,
                end,
                _ALGO_RULES,
            )
            return tuple(map_futures_history_order(row) for row in rows) + tuple(
                map_futures_algo_history_order(row) for row in algo_rows
            )

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

    def active_symbols(self, since: datetime) -> tuple[ActiveSymbol, ...]:
        start, end = span_ms(since, self._clock())
        with history_read_failures(f"{_VENUE} active symbols could not be read"):
            client = self._client()
            positions: list[dict[str, Any]] = client.futures_position_information()
            open_orders: list[dict[str, Any]] = client.futures_get_open_orders()
            open_algo_orders: list[dict[str, Any]] = (
                client.futures_get_open_algo_orders()
            )
            income = fetch_span(
                lambda s, e: client.futures_income_history(
                    startTime=s, endTime=e, limit=_ROW_LIMIT
                ),
                start,
                end,
                _RULES,
            )
            held = {
                row["symbol"]
                for row in positions
                if Decimal(str(row.get("positionAmt", "0"))) != 0
            }
            traded = {row["symbol"] for row in income if row["symbol"]}
            waiting = {row["symbol"] for row in open_orders + open_algo_orders}
            return active_symbols_from(
                [
                    (ActiveReason.OPEN_ORDER, waiting),
                    (ActiveReason.TRADED, traded),
                    (ActiveReason.HELD, held),
                ]
            )

    def every_symbol_scan_limit(self) -> int | None:
        # A seven-day tab is one window per pair, and only pairs actually
        # held, traded or waiting are active: no cap (`BUG-145`).
        return None

    def known_gaps(self) -> HistoryGaps:
        return _GAPS

    def _client(self) -> ITradingSessionClient:
        return self._session_factory.create_trading_client(
            require_credentials(self._credentials_provider, _VENUE)
        )
