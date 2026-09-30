"""`EPIC-028E` — `IAccountHistoryReader` for Spot.

@details `GET /api/v3/allOrders` and `GET /api/v3/myTrades` both need a
symbol, accept at most twenty-four hours between `startTime` and `endTime`,
and return at most 1 000 rows; `fetch_span` turns a seven-day request into
seven or more requests within those limits (weight 20 each, far under
Binance's 6 000 a minute for the handful of pairs a desk shows).

`active_symbols` is every USDT pair of an asset the account holds (ADR D9:
USDT-quoted only) that the exchange actually lists, plus every symbol with an
open order. The listing check matters: a testnet account holds assets with no
USDT pair, and asking `myTrades` for one is an error, not an empty answer. It
also drops the quote asset itself, since no `USDTUSDT` pair exists.

Payload shapes and limits follow Binance's documented Spot API, with the
same live-call disclosure as `spot_account_reader.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_window import (
    HistoryWindowRules,
    fetch_span,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_payload_mapper import (
    map_spot_history_order,
    map_spot_trade,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
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
_READ_FAILURES = (BinanceAPIException, BinanceRequestException, RequestException)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def _held_assets(account: dict[str, Any]) -> set[str]:
    held: set[str] = set()
    for balance in account.get("balances", []):
        try:
            total = Decimal(str(balance.get("free", "0"))) + Decimal(
                str(balance.get("locked", "0"))
            )
        except InvalidOperation:
            continue
        if total > 0:
            held.add(balance["asset"])
    return held


class SpotHistoryReader(IAccountHistoryReader):
    """Reads one Spot account's orders and fills, symbol by symbol."""

    def __init__(
        self,
        session_factory: ISpotSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider
        self._clock = clock

    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        client = self._client()

        def fetch(start: int, end: int) -> list[dict[str, Any]]:
            return client.get_all_orders(
                symbol=symbol, startTime=start, endTime=end, limit=_ROW_LIMIT
            )

        return tuple(map_spot_history_order(row) for row in self._read(fetch, since))

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        client = self._client()

        def fetch(start: int, end: int) -> list[dict[str, Any]]:
            return client.get_my_trades(
                symbol=symbol, startTime=start, endTime=end, limit=_ROW_LIMIT
            )

        return tuple(map_spot_trade(row) for row in self._read(fetch, since))

    def active_symbols(self) -> tuple[str, ...]:
        client = self._client()
        try:
            account = client.get_account()
            open_orders = client.get_open_orders()
        except _READ_FAILURES as exc:
            raise AccountHistoryUnavailableError(
                f"Spot active symbols could not be read: {exc}"
            ) from exc
        listed = {
            symbol
            for symbol in (f"{asset}{_QUOTE_ASSET}" for asset in _held_assets(account))
            if self._metadata_provider.get_or_fetch(symbol) is not None
        }
        return tuple(sorted(listed | {row["symbol"] for row in open_orders}))

    def _read(
        self, fetch: Callable[[int, int], list[dict[str, Any]]], since: datetime
    ) -> list[dict[str, Any]]:
        try:
            return fetch_span(fetch, _ms(since), _ms(self._clock()), _RULES)
        except _READ_FAILURES as exc:
            raise AccountHistoryUnavailableError(
                f"Spot history could not be read: {exc}"
            ) from exc

    def _client(self) -> ISpotSessionClient:
        resolution = self._credentials_provider.resolve()
        if resolution.credentials is None:
            raise AccountHistoryUnavailableError(
                "No Spot credentials configured — cannot read account history."
            )
        try:
            return self._session_factory.create_account_client(resolution.credentials)
        except _READ_FAILURES as exc:
            raise AccountHistoryUnavailableError(
                f"Spot session could not be opened: {exc}"
            ) from exc
