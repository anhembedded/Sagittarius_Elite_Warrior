"""`EPIC-034` D11 — each mainnet venue runs through the same path as its testnet
twin, against the fake Binance server: the owner's variables, the real registry,
the Connect query, the real adapters over HTTP. Only the venue and its key differ.

Not proven here, and not provable from this sandbox (HTTP 451 to `*.binance.com`):
the owner's real balances. That is the owner's manual check, recorded in
`EPIC-034E`. No order is placed by any test here: Connect only reads.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_connection import (
    GetVenueConnectionQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.ensure_session_ready import (
    EnsureSessionReadyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_MAINNET_ENV_API_KEY,
    FUTURES_MAINNET_ENV_API_SECRET,
    SPOT_MAINNET_ENV_API_KEY,
    SPOT_MAINNET_ENV_API_SECRET,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.testnet.grid_testnet_app import (
    SYMBOL,
    composed_on_spot_testnet,
    spot_testnet_config,
)

from .grid_fake_exchange import FakeExchange

_ENV = {
    TradingVenue.SPOT_MAINNET: (SPOT_MAINNET_ENV_API_KEY, SPOT_MAINNET_ENV_API_SECRET),
    TradingVenue.FUTURES_MAINNET: (
        FUTURES_MAINNET_ENV_API_KEY,
        FUTURES_MAINNET_ENV_API_SECRET,
    ),
}
_MAINNETS = list(_ENV)
_PLACING = ("POST", "PUT", "DELETE")


@pytest.fixture
def mainnet_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for key_name, secret_name in _ENV.values():
        monkeypatch.setenv(key_name, "mainnet-key")
        monkeypatch.setenv(secret_name, "mainnet-secret")


@pytest.fixture
def mainnet_urls(exchange: FakeExchange) -> Iterator[None]:
    """python-binance's mainnet hosts, pointed at the fake server (the wallet family
    too, where `apiRestrictions` lives)."""
    urls = exchange.urls
    with (
        patch.object(Client, "API_URL", urls.spot),
        patch.object(Client, "FUTURES_URL", urls.futures),
        patch.object(Client, "MARGIN_API_URL", urls.margin),
    ):
        yield


#: What opening a signed session asks first: the construction ping and the server's
#: time, for the clock offset (`BUG-111`). They read nothing of the account.
_SESSION_OPENING = {"/api/v3/ping", "/api/v3/time", "/fapi/v1/time"}


def _reads(exchange: FakeExchange) -> list[str]:
    """The paths asked, in order, without the session-opening ones."""
    return [path for _, path in exchange.urls.requests if path not in _SESSION_OPENING]


def _connect(exchange: FakeExchange, tmp_path: Path, venue: TradingVenue):
    with composed_on_spot_testnet(spot_testnet_config(tmp_path)) as app:
        exchange.urls.requests.clear()
        return app.engine.dispatch(
            GetVenueConnectionQuery, GetVenueConnectionQuery(venue, SYMBOL)
        )


@pytest.mark.usefixtures("mainnet_keys", "mainnet_urls")
@pytest.mark.parametrize("venue", _MAINNETS)
def test_a_mainnet_venue_is_connected_like_its_testnet_twin(
    exchange: FakeExchange, tmp_path: Path, venue: TradingVenue
) -> None:
    answer = _connect(exchange, tmp_path, venue)

    assert isinstance(answer, VenueAccountSnapshot), answer
    assert answer.source is AccountSource.for_venue(venue)
    assert answer.available > 0
    assert answer.rules.symbol == SYMBOL
    assert answer.price > 0
    assert not [r for r in exchange.urls.requests if r[0] in _PLACING]


@pytest.mark.usefixtures("mainnet_keys", "mainnet_urls")
@pytest.mark.parametrize("venue", _MAINNETS)
def test_the_key_is_asked_what_it_may_do_before_anything_else_is_read(
    exchange: FakeExchange, tmp_path: Path, venue: TradingVenue
) -> None:
    _connect(exchange, tmp_path, venue)

    assert _reads(exchange)[0] == "/sapi/v1/account/apiRestrictions"


@pytest.mark.usefixtures("mainnet_keys", "mainnet_urls")
@pytest.mark.parametrize("venue", _MAINNETS)
def test_a_key_that_can_trade_is_accepted_because_mainnet_trades_like_testnet(
    exchange: FakeExchange, tmp_path: Path, venue: TradingVenue
) -> None:
    exchange.urls.api_restrictions.enable_spot_and_margin_trading = True

    answer = _connect(exchange, tmp_path, venue)

    assert isinstance(answer, VenueAccountSnapshot), answer


@pytest.mark.usefixtures("mainnet_keys", "mainnet_urls")
@pytest.mark.parametrize("venue", _MAINNETS)
def test_a_key_that_can_withdraw_is_refused_before_any_account_is_read(
    exchange: FakeExchange, tmp_path: Path, venue: TradingVenue
) -> None:
    exchange.urls.api_restrictions.enable_withdrawals = True

    answer = _connect(exchange, tmp_path, venue)

    assert answer == ConnectFailure(
        AccountSource.for_venue(venue),
        ConnectionFailureKind.WITHDRAWAL_ENABLED,
        "withdrawals",
    )
    assert _reads(exchange) == ["/sapi/v1/account/apiRestrictions"]


@pytest.mark.usefixtures("mainnet_urls")
@pytest.mark.parametrize("venue", _MAINNETS)
def test_without_the_variables_a_mainnet_venue_has_no_key_and_asks_nothing(
    exchange: FakeExchange,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    venue: TradingVenue,
) -> None:
    for key_name, secret_name in _ENV.values():
        monkeypatch.delenv(key_name, raising=False)
        monkeypatch.delenv(secret_name, raising=False)

    answer = _connect(exchange, tmp_path, venue)

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.NOT_CONFIGURED
    assert exchange.urls.requests == []


@pytest.mark.usefixtures("mainnet_keys", "mainnet_urls")
def test_an_exchange_under_maintenance_is_named_for_a_mainnet_venue_too(
    exchange: FakeExchange, tmp_path: Path
) -> None:
    exchange.urls.maintenance.on = True

    answer = _connect(exchange, tmp_path, TradingVenue.SPOT_MAINNET)

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.MAINTENANCE


@pytest.mark.usefixtures("mainnet_keys", "mainnet_urls")
@pytest.mark.parametrize("venue", _MAINNETS)
def test_a_key_that_can_withdraw_opens_no_order_session_and_reads_nothing_else(
    exchange: FakeExchange, tmp_path: Path, venue: TradingVenue
) -> None:
    """The gate is under every adapter's credentials, not in one reader: the order
    path (`ensure_ready`) and the desk's own account read stop on a key that can
    withdraw, with the Connect step never asked (D5)."""
    exchange.urls.api_restrictions.enable_withdrawals = True

    with composed_on_spot_testnet(spot_testnet_config(tmp_path)) as app:
        exchange.urls.requests.clear()
        opened = app.engine.dispatch(
            EnsureSessionReadyCommand, EnsureSessionReadyCommand(venue=venue)
        )
        desk = app.engine.context.container.resolve(IVenueContexts).get(venue)
        status = desk.account_reader.check_connection()

    assert isinstance(opened, SessionReadyResult)
    assert not opened.ready
    assert opened.block_reason is SessionBlockReason.CONNECTION_NOT_READY
    assert not status.reachable
    # The key gate refused a stored key that can withdraw: the desk says so, not "no key" (BUG-193).
    assert status.failure is ConnectionFailureKind.WITHDRAWAL_ENABLED
    assert set(_reads(exchange)) == {"/sapi/v1/account/apiRestrictions"}
    assert not [r for r in exchange.urls.requests if r[0] in _PLACING]
