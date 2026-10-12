"""`EPIC-038` D9 — `trade-once` exits by whether a restart can fix the failure.

The same rule `exchange-status` and `preflight` follow, through the shared
mapping: a missing, rejected or badly signed key is the operator's (5); a lost
connection, a maintenance page or a rejected clock is a wait (6).
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.cli.trade_once_cmd import (
    _blocked_exit_code,
    execute_trade_once,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .test_trade_once_cmd import _app_ready_to_submit_an_order, _args, _signal


def _unready(kind: ConnectionFailureKind) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=False,
        failure=kind,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        (ConnectionFailureKind.NOT_CONFIGURED, ExitCode.CONFIGURATION),
        (ConnectionFailureKind.KEY_REJECTED, ExitCode.CONFIGURATION),
        (ConnectionFailureKind.BAD_SIGNATURE, ExitCode.CONFIGURATION),
        (ConnectionFailureKind.NETWORK, ExitCode.EXCHANGE),
        (ConnectionFailureKind.MAINTENANCE, ExitCode.EXCHANGE),
        (ConnectionFailureKind.CLOCK_SKEW, ExitCode.EXCHANGE),
    ],
)
def test_an_unknown_balance_exits_by_why_the_connection_failed(
    kind: ConnectionFailureKind, code: ExitCode
):
    app, _submission = _app_ready_to_submit_an_order(_unready(kind))

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.strategy.cli.trade_once_cmd.build_engine"
    ) as mock_build_engine:
        mock_build_engine.return_value.on_tick.return_value = _signal()
        outcome = execute_trade_once(app, _args())

    assert outcome == CliOutcome(code)


def test_a_rejected_key_blocks_the_order_with_the_configuration_exit():
    result = Mock()
    result.blocked_by = ExecuteOrderSafetyGate.KEY_REJECTED

    assert _blocked_exit_code(result) is ExitCode.CONFIGURATION


def test_a_connection_that_is_not_ready_blocks_the_order_with_the_exchange_exit():
    result = Mock()
    result.blocked_by = ExecuteOrderSafetyGate.CONNECTION_NOT_READY

    assert _blocked_exit_code(result) is ExitCode.EXCHANGE


def test_an_order_refused_because_the_key_is_rejected_exits_as_a_configuration_error():
    app, submission = _app_ready_to_submit_an_order()
    submission.submit_raises(
        OrderRejectedByExchangeError(OrderRejectionReason.KEY_REJECTED, "-2015")
    )

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.strategy.cli.trade_once_cmd.build_engine"
    ) as mock_build_engine:
        mock_build_engine.return_value.on_tick.return_value = _signal()
        outcome = execute_trade_once(app, _args())

    assert outcome == CliOutcome(ExitCode.CONFIGURATION)
