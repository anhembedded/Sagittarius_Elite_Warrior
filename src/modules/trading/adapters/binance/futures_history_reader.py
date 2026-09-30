"""`EPIC-028E` — `IAccountHistoryReader` for USD-M Futures.

@details `GET /fapi/v1/allOrders` and `GET /fapi/v1/userTrades` both need a
symbol, accept at most seven days between `startTime` and `endTime`, and
return at most 1 000 rows; `fetch_span` turns any requested span into
requests within those limits. Binance keeps Futures order history for 90
days and trade history for six months, so a `since` older than that reads
what the exchange still has.

`active_symbols` is every symbol with an open position or an open order —
`positionRisk` and `openOrders` without a symbol, the same two reads
`EnableTradingCommandHandler` reconciles against.

Payload shapes and limits follow Binance's documented USD-M API; they were
not re-verified against a live call (egress to `*.binance.*` is blocked in
this sandbox), the same disclosure as `futures_account_reader.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_payload_mapper import (
    map_futures_history_order,
    map_futures_trade,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_window import (
    HistoryWindowRules,
    fetch_span,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
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
_READ_FAILURES = (BinanceAPIException, BinanceRequestException, RequestException)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


class FuturesHistoryReader(IAccountHistoryReader):
    """Reads one Futures account's orders and fills, symbol by symbol."""

    def __init__(
        self,
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._clock = clock

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        client = self._client()

        def fetch(start: int, end: int) -> list[dict[str, Any]]:
            return client.futures_get_all_orders(
                symbol=symbol, startTime=start, endTime=end, limit=_ROW_LIMIT
            )

        return tuple(map_futures_history_order(row) for row in self._read(fetch, since))

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        client = self._client()

        def fetch(start: int, end: int) -> list[dict[str, Any]]:
            return client.futures_account_trades(
                symbol=symbol, startTime=start, endTime=end, limit=_ROW_LIMIT
            )

        return tuple(map_futures_trade(row) for row in self._read(fetch, since))

    def active_symbols(self) -> tuple[str, ...]:
        client = self._client()
        try:
            positions = client.futures_position_information()
            open_orders = client.futures_get_open_orders()
        except _READ_FAILURES as exc:
            raise AccountHistoryUnavailableError(
                f"Futures active symbols could not be read: {exc}"
            ) from exc
        held = {
            row["symbol"]
            for row in positions
            if Decimal(str(row.get("positionAmt", "0"))) != 0
        }
        return tuple(sorted(held | {row["symbol"] for row in open_orders}))

    def _read(
        self, fetch: Callable[[int, int], list[dict[str, Any]]], since: datetime
    ) -> list[dict[str, Any]]:
        try:
            return fetch_span(fetch, _ms(since), _ms(self._clock()), _RULES)
        except _READ_FAILURES as exc:
            raise AccountHistoryUnavailableError(
                f"Futures history could not be read: {exc}"
            ) from exc

    def _client(self) -> ITradingSessionClient:
        resolution = self._credentials_provider.resolve()
        if resolution.credentials is None:
            raise AccountHistoryUnavailableError(
                "No Futures credentials configured — cannot read account history."
            )
        try:
            return self._session_factory.create_trading_client(resolution.credentials)
        except _READ_FAILURES as exc:
            raise AccountHistoryUnavailableError(
                f"Futures session could not be opened: {exc}"
            ) from exc
