"""`EPIC-028E` — what `FuturesHistoryReader` and `SpotHistoryReader` do
around the exchange: which symbols count as active, and how a failed read is
reported.

@details The session factories and the credentials provider are small
subclasses of their ports; only the raw SDK client, which is third-party, is a
`Mock`. The request shapes and the window splitting against a real HTTP round
trip are `tests/integration/infrastructure/binance/
test_history_readers_against_fake_server.py`'s.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.listed_symbols import (
    ListedSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_reader import (
    SpotHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionClient,
    ISpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)

_NOW = datetime(2026, 9, 30, tzinfo=UTC)
_SINCE = _NOW - timedelta(days=7)


class _Credentials(IExchangeCredentialsProvider):
    def __init__(self, configured: bool = True) -> None:
        self._credentials = (
            ExchangeCredentials(api_key="key", api_secret="secret")
            if configured
            else None
        )

    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(self._credentials, CredentialsSource.FILE)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


class _FuturesSessions(ITradingSessionFactory):
    def __init__(self, client: Any) -> None:
        self._client = client

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ITradingSessionClient:
        return self._client


class _SpotSessions(ISpotSessionFactory):
    def __init__(self, client: Any) -> None:
        self._client = client

    def create_account_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        return self._client

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        raise AssertionError("history reads use the account client")


def _listed(symbol: str) -> SymbolOrderMetadata:
    return SymbolOrderMetadata(
        symbol=symbol,
        status="TRADING",
        step_size=Decimal("0.00001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=_NOW,
    )


def _api_error() -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code = -1121
    exc.message = "Invalid symbol."
    exc.status_code = 400
    exc.response = None
    exc.request = None
    return exc


def _futures(
    client: Any, configured: bool = True, offset_ms: int = 0
) -> FuturesHistoryReader:
    client.timestamp_offset = offset_ms
    return FuturesHistoryReader(
        _FuturesSessions(client), _Credentials(configured), lambda: _NOW
    )


class _Catalog(IMarketMetadataProvider):
    """The exchange's symbol catalog, behaving like `SpotMetadataProvider`:
    `get_or_fetch` downloads the whole catalog on a cache miss, `refresh`
    always does. Counts the downloads; can be told to fail."""

    def __init__(self, *listed: str) -> None:
        self.cache = InMemorySymbolOrderMetadataCache()
        self._listed = listed
        self.downloads = 0
        self.failure: Exception | None = None

    def get_or_fetch(self, symbol: str) -> SymbolOrderMetadata | None:
        if not self.cache.has(symbol):
            self.refresh()
        return self.cache.get(symbol)

    def refresh(self) -> None:
        self.downloads += 1
        if self.failure is not None:
            raise self.failure
        for symbol in self._listed:
            self.cache.put(_listed(symbol))


def _spot(
    client: Any, catalog: _Catalog | None = None, offset_ms: int = 0
) -> SpotHistoryReader:
    client.timestamp_offset = offset_ms
    catalog = catalog or _Catalog()
    return SpotHistoryReader(
        _SpotSessions(client),
        _Credentials(),
        ListedSymbols(catalog, catalog.cache),
        lambda: _NOW,
    )


def test_each_reader_states_its_venues_gaps() -> None:
    futures = _futures(Mock()).known_gaps()
    spot = _spot(Mock()).known_gaps()

    assert any("3 days" in gap for gap in futures.order_history)
    assert futures.every_symbol and spot.every_symbol
    assert spot.order_history == ()


def _unlisted_holdings_client() -> Mock:
    """Holds USDT, BTC and two assets with no USDT pair (the PR #297 review's
    probe)."""
    client = Mock()
    client.get_account.return_value = {
        "balances": [
            {"asset": asset, "free": "1", "locked": "0"}
            for asset in ("USDT", "BTC", "XYZ", "ABC")
        ]
    }
    client.get_open_orders.return_value = []
    return client


def test_unlisted_holdings_download_the_catalog_once_not_once_each() -> None:
    catalog = _Catalog("BTCUSDT")
    reader = _spot(_unlisted_holdings_client(), catalog)

    first = reader.active_symbols(_SINCE)
    reader.active_symbols(_SINCE)
    reader.active_symbols(_SINCE)

    assert [pair.symbol for pair in first] == ["BTCUSDT"]
    assert catalog.downloads == 1


def test_the_quote_asset_is_never_looked_up_as_a_pair() -> None:
    """USDT and BTC held, BTCUSDT already cached: nothing is unknown, so no
    download. Looking up `USDTUSDT` would have cost one."""
    catalog = _Catalog("BTCUSDT")
    catalog.refresh()
    catalog.downloads = 0
    client = Mock()
    client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "100", "locked": "0"},
            {"asset": "BTC", "free": "1", "locked": "0"},
        ]
    }
    client.get_open_orders.return_value = []

    held = _spot(client, catalog).active_symbols(_SINCE)
    assert [pair.symbol for pair in held] == ["BTCUSDT"]
    assert catalog.downloads == 0


def test_a_failed_catalog_download_raises_the_readers_own_error() -> None:
    catalog = _Catalog("BTCUSDT")
    catalog.failure = _api_error()

    with pytest.raises(AccountHistoryUnavailableError) as raised:
        _spot(_unlisted_holdings_client(), catalog).active_symbols(_SINCE)

    assert raised.value.__cause__ is catalog.failure


def test_a_read_asks_from_since_up_to_the_clock() -> None:
    client = Mock()
    client.futures_get_all_orders.return_value = []
    client.futures_get_all_algo_orders.return_value = []

    _futures(client).order_history("BTCUSDT", _NOW - timedelta(hours=1))

    kwargs = client.futures_get_all_orders.call_args.kwargs
    assert kwargs["symbol"] == "BTCUSDT"
    assert kwargs["endTime"] == int(_NOW.timestamp() * 1000)
    assert kwargs["startTime"] == int(_NOW.timestamp() * 1000) - 3_600_000


@pytest.mark.parametrize("failure", [_api_error(), RequestsConnectionError("reset")])
def test_a_failed_futures_read_raises_the_readers_own_error(
    failure: Exception,
) -> None:
    client = Mock()
    client.futures_account_trades.side_effect = failure

    with pytest.raises(AccountHistoryUnavailableError) as raised:
        _futures(client).trade_history("BTCUSDT", _NOW - timedelta(days=1))

    assert raised.value.__cause__ is failure


def test_a_failed_spot_read_raises_the_readers_own_error() -> None:
    client = Mock()
    client.get_my_trades.side_effect = _api_error()

    with pytest.raises(AccountHistoryUnavailableError):
        _spot(client).trade_history("BTCUSDT", _NOW - timedelta(hours=2))


@pytest.mark.parametrize("reader", ["futures", "spot"])
def test_a_span_further_back_than_the_lookback_is_refused_unasked(
    reader: str,
) -> None:
    client = Mock()
    subject = _futures(client) if reader == "futures" else _spot(client)

    with pytest.raises(ValueError, match="30 days"):
        subject.trade_history("BTCUSDT", _NOW - timedelta(days=30, seconds=1))

    assert client.method_calls == []


def test_a_span_exactly_at_the_lookback_is_read() -> None:
    client = Mock()
    client.get_all_orders.return_value = []

    _spot(client).order_history("BTCUSDT", _NOW - timedelta(days=30))

    # Both ends are inclusive: thirty whole days, then the last millisecond.
    assert client.get_all_orders.call_count == 31


def test_no_credentials_raises_before_any_request() -> None:
    client = Mock()

    with pytest.raises(AccountHistoryUnavailableError):
        _futures(client, configured=False).order_history("BTCUSDT", _NOW)

    client.futures_get_all_orders.assert_not_called()


#: `EPIC-028Q` — a row missing a field, and a row with a number Binance never
#: sends. Before the fix the mapping ran outside the error translation, so
#: these escaped as `KeyError` and `InvalidOperation`.
_MALFORMED_ROWS = [{"symbol": "BTCUSDT"}, {"symbol": "BTCUSDT", "price": "abc"}]


@pytest.mark.parametrize("row", _MALFORMED_ROWS)
def test_a_malformed_futures_row_is_reported_as_unavailable_history(
    row: dict[str, Any],
) -> None:
    client = Mock()
    client.futures_get_all_orders.return_value = [row]
    client.futures_account_trades.return_value = [row]
    reader = _futures(client)

    with pytest.raises(AccountHistoryUnavailableError, match="malformed"):
        reader.order_history("BTCUSDT", _NOW - timedelta(days=1))
    with pytest.raises(AccountHistoryUnavailableError, match="malformed"):
        reader.trade_history("BTCUSDT", _NOW - timedelta(days=1))


@pytest.mark.parametrize("row", _MALFORMED_ROWS)
def test_a_malformed_spot_row_is_reported_as_unavailable_history(
    row: dict[str, Any],
) -> None:
    client = Mock()
    client.get_all_orders.return_value = [row]
    client.get_my_trades.return_value = [row]
    reader = _spot(client)

    with pytest.raises(AccountHistoryUnavailableError, match="malformed"):
        reader.order_history("BTCUSDT", _NOW - timedelta(hours=1))
    with pytest.raises(AccountHistoryUnavailableError, match="malformed"):
        reader.trade_history("BTCUSDT", _NOW - timedelta(hours=1))


def test_a_malformed_futures_position_row_is_reported_as_unavailable() -> None:
    client = Mock()
    client.futures_position_information.return_value = [
        {"symbol": "BTCUSDT", "positionAmt": "not a number"}
    ]
    client.futures_get_open_orders.return_value = []
    client.futures_income_history.return_value = []

    with pytest.raises(AccountHistoryUnavailableError, match="malformed"):
        _futures(client).active_symbols(_SINCE)
