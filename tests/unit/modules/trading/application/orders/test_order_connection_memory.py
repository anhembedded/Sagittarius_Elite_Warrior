"""`BUG-247` - a passing connection check serves the orders of the next beat; a failing one never."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.connection_gate import (
    order_connection_block,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_connection_memory import (
    ORDER_CONNECTION_REUSE_SECONDS,
    OrderConnectionMemory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_VENUE = TradingVenue.FUTURES_TESTNET


def _status(
    failure: ConnectionFailureKind | None = None, retry_after: timedelta | None = None
) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=_VENUE,
        reachable=failure is None,
        failure=failure,
        server_time_skew_ms=0,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        retry_after=retry_after,
    )


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _scope(
    reader: FakeTradingAccountReader, memory: OrderConnectionMemory
) -> VenueTradingScope:
    return VenueTradingScope(
        venue=_VENUE,
        ports=fake_venue_context(_VENUE, account_reader=reader),
        session_state=TradingSessionState(),
        equity_recorder=EquityCurveRecorder(),
        order_connection=memory,
    )


def test_fifty_orders_inside_a_beat_check_the_connection_once() -> None:
    reader = FakeTradingAccountReader(_status())
    clock = _Clock()
    scope = _scope(reader, OrderConnectionMemory(clock))

    blocks = [order_connection_block(scope) for _ in range(50)]

    assert blocks == [None] * 50
    assert reader.checks == 1


def test_the_check_is_made_again_when_the_beat_is_over() -> None:
    reader = FakeTradingAccountReader(_status())
    clock = _Clock()
    scope = _scope(reader, OrderConnectionMemory(clock))
    order_connection_block(scope)

    clock.now += ORDER_CONNECTION_REUSE_SECONDS - 0.01
    order_connection_block(scope)
    assert reader.checks == 1, "still inside the window"

    clock.now += 0.01
    order_connection_block(scope)
    assert reader.checks == 2, "the window is over at its edge"


@pytest.mark.parametrize(
    "failure", [ConnectionFailureKind.KEY_REJECTED, ConnectionFailureKind.NETWORK]
)
def test_a_failed_check_is_never_kept_and_blocks_each_order(
    failure: ConnectionFailureKind,
) -> None:
    reader = FakeTradingAccountReader(_status(failure))
    scope = _scope(reader, OrderConnectionMemory(_Clock()))

    first = order_connection_block(scope)
    second = order_connection_block(scope)

    assert first is not None
    assert second is first
    assert reader.checks == 2


def test_a_failure_after_a_pass_blocks_the_order_that_finds_it() -> None:
    reader = FakeTradingAccountReader(_status())
    clock = _Clock()
    scope = _scope(reader, OrderConnectionMemory(clock))
    assert order_connection_block(scope) is None

    reader.answer_with(_status(ConnectionFailureKind.KEY_REJECTED))
    clock.now += ORDER_CONNECTION_REUSE_SECONDS
    assert order_connection_block(scope) is ExecuteOrderSafetyGate.KEY_REJECTED
    reader.answer_with(_status())
    assert order_connection_block(scope) is None
    assert reader.checks == 3, "the failure dropped what the pass had kept"


def test_a_pause_is_raised_for_each_order_and_never_kept() -> None:
    reader = FakeTradingAccountReader(
        _status(ConnectionFailureKind.RATE_LIMITED, timedelta(seconds=9))
    )
    scope = _scope(reader, OrderConnectionMemory(_Clock()))

    for _ in range(2):
        with pytest.raises(ExchangeRateLimitedError):
            order_connection_block(scope)

    assert reader.checks == 2


def test_a_slow_pass_does_not_bring_back_what_a_later_failure_cleared() -> None:
    """Check A begins first and is slow; check B begins later and fails; A then ends with a pass."""

    class _Overtaken(FakeTradingAccountReader):
        def __init__(self) -> None:
            super().__init__(_status())
            self.during_slow: Callable[[], None] = lambda: None

        def check_connection(self) -> ExchangeConnectionStatus:
            self.checks += 1
            if self.checks == 1:
                self.during_slow()
            return self._answer

    reader = _Overtaken()
    reader._answer = _status()
    memory = OrderConnectionMemory(_Clock())

    def fail_in_between() -> None:
        reader._answer = _status(ConnectionFailureKind.KEY_REJECTED)
        assert memory.status(reader).failure is ConnectionFailureKind.KEY_REJECTED
        reader._answer = _status()

    reader.during_slow = fail_in_between
    memory.status(reader)  # A: slow, ends with a pass

    memory.status(reader)
    assert reader.checks == 3, "the older pass was not kept over the newer failure"
