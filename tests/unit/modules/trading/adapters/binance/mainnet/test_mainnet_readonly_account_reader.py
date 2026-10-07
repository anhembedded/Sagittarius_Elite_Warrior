"""`EPIC-034E` — the read-only mainnet reader's decisions, on a scripted client.

The client implements the real `IMainnetReadClient` port and records every call
it gets, so a test can say which reads happened and which never did. The HTTP
round trip is the integration test's.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_permissions_parser import (
    parse_key_permissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_readonly_account_reader import (
    MainnetReadOnlyAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_credentials_resolver import (
    ICredentialsResolver,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_mainnet_read_client import (
    IMainnetReadClient,
    IMainnetReadSessionFactory,
)

_SOURCE = AccountSource.SPOT_MAINNET_READONLY
_NOW = datetime(2026, 10, 7, tzinfo=UTC)
_READ_ONLY = {
    "enableReading": True,
    "enableSpotAndMarginTrading": False,
    "enableWithdrawals": False,
}
_ACCOUNT = {
    "canTrade": True,
    "commissionRates": {"maker": "0.001", "taker": "0.001"},
    "balances": [{"asset": "USDT", "free": "250.5", "locked": "10"}],
}
_EXCHANGE_INFO = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                {"filterType": "LOT_SIZE", "stepSize": "0.00001"},
                {"filterType": "NOTIONAL", "minNotional": "5"},
            ],
        }
    ]
}
_BOOK = {
    "symbol": "BTCUSDT",
    "bidPrice": "99",
    "bidQty": "1",
    "askPrice": "101",
    "askQty": "1",
}


class _Client:
    """Scripted reads; a value that is an exception is raised."""

    def __init__(self, **answers: Any) -> None:
        self.answers: dict[str, Any] = {
            "get_account_api_permissions": _READ_ONLY,
            "get_account": _ACCOUNT,
            "get_open_orders": [],
            "get_exchange_info": _EXCHANGE_INFO,
            "get_orderbook_ticker": _BOOK,
            **answers,
        }
        self.calls: list[str] = []

    def _answer(self, name: str) -> Any:
        self.calls.append(name)
        answer = self.answers[name]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def ping(self) -> dict[str, Any]:
        return {}

    def get_server_time(self) -> dict[str, Any]:
        return {"serverTime": 0}

    def get_account(self, **params: Any) -> dict[str, Any]:
        return self._answer("get_account")

    def get_account_api_permissions(self, **params: Any) -> dict[str, Any]:
        return self._answer("get_account_api_permissions")

    def get_open_orders(self, **params: Any) -> list[dict[str, Any]]:
        return self._answer("get_open_orders")

    def get_orderbook_ticker(self, **params: Any) -> dict[str, Any]:
        return self._answer("get_orderbook_ticker")

    def get_exchange_info(self, **params: Any) -> dict[str, Any]:
        return self._answer("get_exchange_info")


class _Clients(IMainnetReadSessionFactory):
    def __init__(self, client: IMainnetReadClient | Exception) -> None:
        self._client = client

    def create_read_client(
        self, credentials: ExchangeCredentials
    ) -> IMainnetReadClient:
        if isinstance(self._client, Exception):
            raise self._client
        return self._client


class _Keys(ICredentialsResolver):
    def __init__(self, credentials: ExchangeCredentials | None) -> None:
        self._credentials = credentials

    def resolve(self) -> ResolvedCredentials:
        source = (
            CredentialsSource.NONE
            if self._credentials is None
            else CredentialsSource.ENV
        )
        return ResolvedCredentials(self._credentials, source)


def _api_error(code: int) -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code, exc.message, exc.status_code, exc.response, exc.request = (
        code,
        f"error {code}",
        400,
        None,
        None,
    )
    return exc


def _reader(client: IMainnetReadClient | Exception, keyed: bool = True):
    keys = _Keys(ExchangeCredentials("k", "s") if keyed else None)
    return MainnetReadOnlyAccountReader(keys, _Clients(client), clock=lambda: _NOW)


def test_a_read_only_key_gives_the_snapshot_the_screen_shows() -> None:
    client = _Client()

    answer = _reader(client).read("BTCUSDT")

    assert isinstance(answer, VenueAccountSnapshot)
    assert str(answer.available) == "250.5"
    assert answer.read_at == _NOW
    assert answer.can_trade is True
    assert answer.open_order_count == 0
    assert answer.key_permissions is not None and answer.key_permissions.is_read_only
    assert str(answer.price) == "101"
    assert client.calls[0] == "get_account_api_permissions"


def test_a_key_that_can_withdraw_reads_nothing_after_its_permissions() -> None:
    client = _Client(
        get_account_api_permissions={**_READ_ONLY, "enableWithdrawals": True}
    )

    answer = _reader(client).read("BTCUSDT")

    assert answer == ConnectFailure(
        _SOURCE, ConnectionFailureKind.WITHDRAWAL_ENABLED, "withdrawals"
    )
    assert client.calls == ["get_account_api_permissions"]


def test_a_key_that_can_withdraw_and_trade_is_refused_for_withdrawing() -> None:
    both = {**_READ_ONLY, "enableWithdrawals": True, "enableSpotAndMarginTrading": True}

    answer = _reader(_Client(get_account_api_permissions=both)).read("BTCUSDT")

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.WITHDRAWAL_ENABLED


def test_no_key_is_not_configured_and_nothing_is_opened() -> None:
    boom = AssertionError("a session was opened with no key")

    answer = _reader(boom, keyed=False).read("BTCUSDT")

    assert answer == ConnectFailure(_SOURCE, ConnectionFailureKind.NOT_CONFIGURED)


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        (-2015, ConnectionFailureKind.KEY_REJECTED),
        (-1022, ConnectionFailureKind.BAD_SIGNATURE),
        (-1021, ConnectionFailureKind.CLOCK_SKEW),
    ],
)
def test_the_exchange_rejecting_the_key_is_named(
    code: int, kind: ConnectionFailureKind
) -> None:
    client = _Client(get_account_api_permissions=_api_error(code))

    answer = _reader(client).read("BTCUSDT")

    assert answer == ConnectFailure(_SOURCE, kind, "")


def test_a_session_that_cannot_be_opened_is_named_by_its_error() -> None:
    answer = _reader(_api_error(-2015)).read("BTCUSDT")

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.KEY_REJECTED


@pytest.mark.parametrize(
    ("read", "what"),
    [
        ("get_account", "the account"),
        ("get_open_orders", "the account"),
        ("get_exchange_info", "the account"),
        ("get_orderbook_ticker", "the account"),
    ],
)
def test_a_read_that_fails_after_the_permissions_is_a_named_failure(
    read: str, what: str
) -> None:
    client = _Client(**{read: RuntimeError("unreachable")})
    client.answers[read] = _api_error(-1000)

    answer = _reader(client).read("BTCUSDT")

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.NETWORK
    assert answer.detail == what


def test_an_account_without_commission_rates_is_unreadable_not_free() -> None:
    answer = _reader(_Client(get_account={"balances": []})).read("BTCUSDT")

    assert isinstance(answer, ConnectFailure)
    assert answer.detail == "the account"


def test_a_symbol_the_exchange_does_not_list_is_named() -> None:
    answer = _reader(_Client(get_orderbook_ticker={**_BOOK, "symbol": "ETHUSDT"})).read(
        "ETHUSDT"
    )

    assert isinstance(answer, ConnectFailure)
    assert "ETHUSDT is not listed" in answer.detail


def test_a_book_with_no_orders_is_no_price() -> None:
    empty = {**_BOOK, "bidQty": "0", "askQty": "0"}

    answer = _reader(_Client(get_orderbook_ticker=empty)).read("BTCUSDT")

    assert isinstance(answer, ConnectFailure)
    assert answer.detail.startswith("the price")


def test_the_reader_is_the_mainnet_source() -> None:
    assert _reader(_Client()).source is _SOURCE


# -- the permissions parser ---------------------------------------------------


def test_the_parser_reads_the_three_flags_the_app_decides_on() -> None:
    permissions = parse_key_permissions(
        {
            "enableReading": True,
            "enableSpotAndMarginTrading": True,
            "enableWithdrawals": False,
        }
    )

    assert (
        permissions.can_read,
        permissions.can_trade_spot,
        permissions.can_withdraw,
    ) == (
        True,
        True,
        False,
    )
    assert not permissions.is_read_only


@pytest.mark.parametrize("missing", list(_READ_ONLY))
def test_a_missing_flag_is_an_error_never_a_false(missing: str) -> None:
    payload = {k: v for k, v in _READ_ONLY.items() if k != missing}

    with pytest.raises(KeyError):
        parse_key_permissions(payload)


@pytest.mark.parametrize("junk", ["false", 0, None])
def test_a_flag_that_is_not_a_boolean_is_an_error(junk: object) -> None:
    with pytest.raises(TypeError):
        parse_key_permissions({**_READ_ONLY, "enableWithdrawals": junk})


def test_a_withdrawal_flag_the_exchange_leaves_out_refuses_the_key() -> None:
    payload = {k: v for k, v in _READ_ONLY.items() if k != "enableWithdrawals"}

    answer = _reader(_Client(get_account_api_permissions=payload)).read("BTCUSDT")

    assert isinstance(answer, ConnectFailure)
    assert answer.detail == "the key's permissions"
    assert answer.kind is not ConnectionFailureKind.NOT_CONFIGURED
