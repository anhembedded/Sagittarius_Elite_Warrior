"""`BUG-209` — a refresh that fails tick after tick is a WARNING once, then an INFO when it recovers.

`PositionRefreshService` and `HoldingsRefreshService` logged every failure at DEBUG, so a
run that lost its account reads for a day was indistinguishable from a healthy one in the
journal. They now follow `AccountSummaryRefreshService`: one WARNING per streak (a line per
tick would be a hot loop, `logging-rule.md` §6) and one INFO when a read works again.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.holdings_refresh_service import (
    HoldingsRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_refresh_service import (
    PositionRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

VENUE = TradingVenue.FUTURES_TESTNET


class _Refreshing(Protocol):
    def refresh_once(self) -> None: ...


def _positions(dispatcher: Mock, session: TradingSessionState) -> _Refreshing:
    return PositionRefreshService(dispatcher, Mock(), session, VENUE)


def _holdings(dispatcher: Mock, session: TradingSessionState) -> _Refreshing:
    return HoldingsRefreshService(dispatcher, Mock(), session, VENUE)


_SERVICES: list[tuple[str, str, Callable[[Mock, TradingSessionState], _Refreshing]]] = [
    ("App.PositionRefresh", "Position refresh", _positions),
    ("App.HoldingsRefresh", "Holdings refresh", _holdings),
]


@pytest.fixture
def session() -> TradingSessionState:
    state = TradingSessionState()
    state.enable(set())
    return state


@pytest.mark.parametrize(("logger_name", "what", "build"), _SERVICES)
def test_a_failure_streak_is_one_warning_and_a_recovery_is_one_info(
    caplog: pytest.LogCaptureFixture,
    session: TradingSessionState,
    logger_name: str,
    what: str,
    build: Callable[[Mock, TradingSessionState], _Refreshing],
) -> None:
    dispatcher = Mock()
    service = build(dispatcher, session)
    dispatcher.dispatch.side_effect = ConnectionError("read timed out")

    with caplog.at_level(logging.DEBUG, logger=logger_name):
        for _ in range(5):
            service.refresh_once()
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 1, "five failed ticks, one WARNING"
        assert what in warnings[0].getMessage()
        assert "read timed out" in warnings[0].getMessage()

        dispatcher.dispatch.side_effect = None
        dispatcher.dispatch.return_value = ()
        service.refresh_once()
        service.refresh_once()

    recovered = [r for r in caplog.records if "[refresh-recovered]" in r.getMessage()]
    assert [r.levelno for r in recovered] == [logging.INFO], (
        "one INFO, at the first success"
    )
    assert "5 failed attempt" in recovered[0].getMessage()


@pytest.mark.parametrize(("logger_name", "what", "build"), _SERVICES)
def test_a_second_streak_warns_again(
    caplog: pytest.LogCaptureFixture,
    session: TradingSessionState,
    logger_name: str,
    what: str,
    build: Callable[[Mock, TradingSessionState], _Refreshing],
) -> None:
    dispatcher = Mock()
    service = build(dispatcher, session)

    with caplog.at_level(logging.DEBUG, logger=logger_name):
        for outcome in (ConnectionError("down"), None, ConnectionError("down again")):
            dispatcher.dispatch.side_effect = outcome
            dispatcher.dispatch.return_value = ()
            service.refresh_once()

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2, "each streak announces itself"


@pytest.mark.parametrize(("logger_name", "what", "build"), _SERVICES)
def test_a_healthy_refresh_writes_nothing_above_debug(
    caplog: pytest.LogCaptureFixture,
    session: TradingSessionState,
    logger_name: str,
    what: str,
    build: Callable[[Mock, TradingSessionState], _Refreshing],
) -> None:
    dispatcher = Mock()
    dispatcher.dispatch.return_value = ()
    service = build(dispatcher, session)

    with caplog.at_level(logging.DEBUG, logger=logger_name):
        service.refresh_once()
        service.refresh_once()

    assert [r for r in caplog.records if r.levelno >= logging.INFO] == []
