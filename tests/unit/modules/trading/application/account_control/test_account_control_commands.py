"""`EPIC-028F` — `ChangeLeverageCommand` and `ChangeMarginTypeCommand`: what
is refused before anything is sent, what reaches the exchange, and how its
answer comes back.

@details The handlers run over the real Futures adapters
(`FuturesAccountControl`, `FuturesTradingClientFactory`); only the raw SDK
session, which is third-party, is a `Mock`, and the session factory counts
how many sessions were opened, so "refused before any network call" is an
assertion on that count.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_leverage import (
    ChangeLeverageCommand,
    ChangeLeverageCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_margin_type import (
    ChangeMarginTypeCommand,
    ChangeMarginTypeCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlRefusal,
    AccountControlResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

_FUTURES = TradingVenue.FUTURES_TESTNET

_OPEN_BTC_POSITION = {
    "symbol": "BTCUSDT",
    "positionAmt": "0.01",
    "entryPrice": "64000",
    "markPrice": "64100",
    "unRealizedProfit": "1",
    "notional": "641.00",
    "initialMargin": "64.10",
    "isolatedMargin": "0",
}


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="key", api_secret="secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used")


class _Sessions(ITradingSessionFactory):
    """Hands out the one raw client and counts the sessions opened."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self.opened = 0

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ITradingSessionClient:
        self.opened += 1
        return self.client


class _CountingAccountReader(FakeTradingAccountReader):
    def __init__(self, status: ExchangeConnectionStatus) -> None:
        super().__init__(status)
        self.checks = 0

    def check_connection(self) -> ExchangeConnectionStatus:
        self.checks += 1
        return super().check_connection()


def _status(
    venue: TradingVenue,
    *,
    reachable: bool = True,
    failure: ConnectionFailureKind | None = None,
) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=venue,
        reachable=reachable,
        failure=failure,
        server_time_skew_ms=0 if reachable else None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=0,
    )


@dataclass
class _Desk:
    """One venue's handlers over a raw client the test arranges."""

    raw: Mock
    sessions: _Sessions
    account_reader: _CountingAccountReader
    leverage: ChangeLeverageCommandHandler
    margin: ChangeMarginTypeCommandHandler


def _desk(
    venue: TradingVenue = _FUTURES,
    *,
    enabled: bool = True,
    status: ExchangeConnectionStatus | None = None,
) -> _Desk:
    raw = Mock()
    raw.futures_position_information.return_value = []
    sessions = _Sessions(raw)
    credentials = _Credentials()
    account_reader = _CountingAccountReader(status or _status(venue))
    context = venue_context(
        venue,
        account_reader=account_reader,
        client_factory=FuturesTradingClientFactory(sessions, credentials, Mock()),
    )
    if context.account_control is not None:
        context = replace(
            context, account_control=FuturesAccountControl(sessions, credentials)
        )
    state = TradingSessionState()
    if enabled:
        state.enable(set())
    scopes = single_venue_scopes(context, state)
    return _Desk(
        raw,
        sessions,
        account_reader,
        ChangeLeverageCommandHandler(scopes),
        ChangeMarginTypeCommandHandler(scopes),
    )


def _to_ten_x(desk: _Desk, venue: TradingVenue = _FUTURES) -> AccountControlResult[Any]:
    return desk.leverage.execute(ChangeLeverageCommand("BTCUSDT", 10, venue=venue))


def _to_isolated(
    desk: _Desk, venue: TradingVenue = _FUTURES
) -> AccountControlResult[Any]:
    return desk.margin.execute(
        ChangeMarginTypeCommand("BTCUSDT", MarginType.ISOLATED, venue=venue)
    )


#: Each command, run on a desk, as one parameter.
_EITHER_COMMAND = pytest.mark.parametrize(
    "change", [_to_ten_x, _to_isolated], ids=["leverage", "margin_type"]
)

Change = Callable[..., AccountControlResult[Any]]


def _api_error(code: int, message: str) -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code = code
    exc.message = message
    exc.status_code = 400
    exc.response = None
    exc.request = None
    return exc


def test_a_leverage_change_reports_the_exchanges_answer() -> None:
    desk = _desk()
    desk.raw.futures_change_leverage.return_value = {
        "symbol": "BTCUSDT",
        "leverage": 10,
        "maxNotionalValue": "10000000",
    }

    result = _to_ten_x(desk)

    assert result.blocked_by is None
    assert result.applied == LeverageSetting("BTCUSDT", 10, Decimal(10000000))
    desk.raw.futures_change_leverage.assert_called_once_with(
        symbol="BTCUSDT", leverage=10
    )


def test_a_margin_type_change_sends_binances_spelling() -> None:
    desk = _desk()
    desk.raw.futures_change_margin_type.return_value = {"code": 200, "msg": "success"}

    result = _to_isolated(desk)

    assert result.blocked_by is None
    assert result.applied is MarginType.ISOLATED
    desk.raw.futures_change_margin_type.assert_called_once_with(
        symbol="BTCUSDT", marginType="ISOLATED"
    )


def test_asking_for_the_margin_type_already_in_effect_is_not_a_refusal() -> None:
    desk = _desk()
    desk.raw.futures_change_margin_type.side_effect = _api_error(
        -4046, "No need to change margin type."
    )

    result = _to_isolated(desk)

    assert result.blocked_by is None
    assert result.applied is MarginType.ISOLATED


@_EITHER_COMMAND
def test_an_exchange_refusal_comes_back_with_its_code_and_message(
    change: Change,
) -> None:
    desk = _desk()
    refusal = _api_error(-4028, "Leverage 10 is not valid")
    desk.raw.futures_change_leverage.side_effect = refusal
    desk.raw.futures_change_margin_type.side_effect = refusal

    result = change(desk)

    assert result.blocked_by is AccountControlRefusal.EXCHANGE_REJECTED
    assert result.applied is None
    assert result.detail == "-4028: Leverage 10 is not valid"


@_EITHER_COMMAND
def test_an_open_position_is_refused_before_the_change_is_sent(
    change: Change,
) -> None:
    desk = _desk()
    desk.raw.futures_position_information.return_value = [_OPEN_BTC_POSITION]

    result = change(desk)

    assert result.blocked_by is AccountControlRefusal.POSITION_OPEN
    assert result.detail == "BTCUSDT has an open position of 0.01"
    desk.raw.futures_position_information.assert_called_once_with(symbol="BTCUSDT")
    desk.raw.futures_change_leverage.assert_not_called()
    desk.raw.futures_change_margin_type.assert_not_called()


@_EITHER_COMMAND
def test_the_spot_venue_is_refused_before_any_network_call(change: Change) -> None:
    spot = TradingVenue.SPOT_TESTNET
    desk = _desk(spot)

    result = change(desk, spot)

    assert result.blocked_by is AccountControlRefusal.NOT_A_FUTURES_VENUE
    assert desk.sessions.opened == 0
    assert desk.account_reader.checks == 0


@_EITHER_COMMAND
def test_the_disabled_venue_is_refused_before_any_network_call(
    change: Change,
) -> None:
    disabled = TradingVenue.DISABLED
    desk = _desk(disabled)

    result = change(desk, disabled)

    assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
    assert desk.sessions.opened == 0
    assert desk.account_reader.checks == 0


@_EITHER_COMMAND
def test_the_trading_switch_off_is_refused_before_any_network_call(
    change: Change,
) -> None:
    desk = _desk(enabled=False)

    result = change(desk)

    assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
    assert desk.sessions.opened == 0
    assert desk.account_reader.checks == 0


@_EITHER_COMMAND
@pytest.mark.parametrize(
    "status",
    [
        _status(_FUTURES, reachable=False),
        _status(_FUTURES, failure=ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED),
    ],
    ids=["unreachable", "reachable_but_failed"],
)
def test_a_connection_that_is_not_ready_sends_nothing(
    change: Change, status: ExchangeConnectionStatus
) -> None:
    desk = _desk(status=status)

    result = change(desk)

    assert result.blocked_by is ExecuteOrderSafetyGate.CONNECTION_NOT_READY
    assert desk.sessions.opened == 0


@_EITHER_COMMAND
def test_an_exchange_that_never_answers_raises(change: Change) -> None:
    desk = _desk()
    failure = RequestsConnectionError("reset")
    desk.raw.futures_change_leverage.side_effect = failure
    desk.raw.futures_change_margin_type.side_effect = failure

    with pytest.raises(AccountControlUnavailableError) as raised:
        change(desk)

    assert raised.value.__cause__ is failure


@pytest.mark.parametrize("leverage", [0, 126])
def test_a_leverage_outside_binances_range_is_refused_at_construction(
    leverage: int,
) -> None:
    with pytest.raises(ValueError, match="1 to 125"):
        ChangeLeverageCommand("BTCUSDT", leverage, venue=_FUTURES)


@pytest.mark.parametrize("leverage", [1, 125])
def test_the_ends_of_binances_leverage_range_are_accepted(leverage: int) -> None:
    assert ChangeLeverageCommand("BTCUSDT", leverage, venue=_FUTURES).leverage == (
        leverage
    )


def test_a_result_is_either_refused_or_applied() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        AccountControlResult(None, None)
    with pytest.raises(ValueError, match="exactly one"):
        AccountControlResult(
            AccountControlRefusal.POSITION_OPEN, MarginType.CROSSED, None
        )
