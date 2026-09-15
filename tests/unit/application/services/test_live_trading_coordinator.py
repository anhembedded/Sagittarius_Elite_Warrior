from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.live_trading_coordinator import (
    LiveTradingCoordinator,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.live_order_blocked_event import (
    LiveOrderBlockedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def _metadata() -> FuturesSymbolMetadata:
    return FuturesSymbolMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _status(usdt_balance: Decimal | None = Decimal(1000)) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=usdt_balance,
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=0,
    )


def _coordinator(
    submission: FakeOrderSubmission,
    live_symbol: str = "BTCUSDT",
    event_publisher: Mock | None = None,
    sizing_percent: float = 20.0,
    leverage: float = 1.0,
) -> LiveTradingCoordinator:
    account_reader = Mock()
    account_reader.check_connection.return_value = _status()
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = _metadata()
    return LiveTradingCoordinator(
        live_symbol,
        submission,
        account_reader,
        metadata_provider,
        event_publisher if event_publisher is not None else Mock(),
        sizing_percent,
        leverage,
    )


def _signal(symbol: str = "BTCUSDT", action: SignalAction = SignalAction.BUY) -> Signal:
    return Signal(
        symbol=symbol,
        action=action,
        reason="test",
        price=64000.0,
        time=datetime(2026, 8, 27, tzinfo=UTC),
    )


def test_ignores_a_signal_for_a_different_symbol() -> None:
    submission = FakeOrderSubmission()
    coordinator = _coordinator(submission, live_symbol="BTCUSDT")

    coordinator.handle(_signal(symbol="ETHUSDT"))

    assert submission.submitted_live == []
    assert submission.submitted_dry == []


def test_submits_one_live_order_for_a_matching_buy_signal() -> None:
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))
    coordinator = _coordinator(submission)

    coordinator.handle(_signal(action=SignalAction.BUY))

    # Landing in `submitted_live` IS the `live=True` assertion, and a
    # stronger one: the fake keeps live and dry in separate lists, so a
    # caller that dropped the flag shows up as an empty list here rather than
    # as a recorded call with the wrong argument.
    (request,) = submission.submitted_live
    assert submission.submitted_dry == []
    assert request.symbol == "BTCUSDT"
    assert request.side is OrderSide.BUY
    assert request.reduce_only is False
    assert request.quantity > 0


def test_short_signal_sets_reduce_only_false_and_sell_side() -> None:
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))
    coordinator = _coordinator(submission)

    coordinator.handle(_signal(action=SignalAction.SHORT))

    (request,) = submission.submitted_live
    assert request.side is OrderSide.SELL
    assert request.reduce_only is False


def test_cover_signal_sets_reduce_only_true() -> None:
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))
    coordinator = _coordinator(submission)

    coordinator.handle(_signal(action=SignalAction.COVER))

    (request,) = submission.submitted_live
    assert request.side is OrderSide.BUY
    assert request.reduce_only is True


def test_no_known_balance_sends_nothing() -> None:
    submission = FakeOrderSubmission()
    account_reader = Mock()
    account_reader.check_connection.return_value = _status(usdt_balance=None)
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = _metadata()
    coordinator = LiveTradingCoordinator(
        "BTCUSDT", submission, account_reader, metadata_provider, Mock(), 20.0, 1.0
    )

    coordinator.handle(_signal())

    assert submission.submitted_live == []
    assert submission.submitted_dry == []


def test_sizing_percent_and_leverage_are_config_driven_not_hardcoded() -> None:
    """`BUG-084` — `LiveTradingCoordinator` used to compute every order off
    a hardcoded 20%/1x, next to `trading.max_notional_per_order_usdt`'s 500
    USDT cap that left almost no account balance able to place an order.
    Two coordinators built with different `sizing_percent` must produce
    different order quantities for the same balance/price."""
    small = FakeOrderSubmission()
    small.submit_answers(ExecuteOrderResult(None, None, (), None))
    _coordinator(small, sizing_percent=10.0).handle(_signal())
    (small_request,) = small.submitted_live

    large = FakeOrderSubmission()
    large.submit_answers(ExecuteOrderResult(None, None, (), None))
    _coordinator(large, sizing_percent=50.0).handle(_signal())
    (large_request,) = large.submitted_live

    assert large_request.quantity > small_request.quantity


def test_a_blocked_order_publishes_a_live_order_blocked_event() -> None:
    """`BUG-084` — before this fix, a blocked order was a log line only;
    nothing reached the Trading screen to distinguish "no signal fired"
    from "a signal fired but got blocked"."""
    submission = FakeOrderSubmission()
    submission.submit_answers(
        ExecuteOrderResult("max_notional_per_order", None, (), None)
    )
    event_publisher = Mock()
    coordinator = _coordinator(submission, event_publisher=event_publisher)

    coordinator.handle(_signal())

    event_publisher.publish.assert_called_once()
    (published,) = event_publisher.publish.call_args.args
    assert isinstance(published, LiveOrderBlockedEvent)
    assert published.symbol == "BTCUSDT"
    assert "max_notional_per_order" in published.reason


def test_an_accepted_order_does_not_publish_a_blocked_event() -> None:
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))
    event_publisher = Mock()
    coordinator = _coordinator(submission, event_publisher=event_publisher)

    coordinator.handle(_signal())

    event_publisher.publish.assert_not_called()


def test_a_zero_computed_quantity_publishes_a_live_order_blocked_event() -> None:
    """`BUG-084` — a balance too small to clear even one `step_size` unit
    used to be a silent `logger.debug()` line, indistinguishable on the
    Trading screen from no signal having fired at all."""
    submission = FakeOrderSubmission()
    account_reader = Mock()
    account_reader.check_connection.return_value = _status(usdt_balance=Decimal(1))
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = _metadata()
    event_publisher = Mock()
    coordinator = LiveTradingCoordinator(
        "BTCUSDT",
        submission,
        account_reader,
        metadata_provider,
        event_publisher,
        20.0,
        1.0,
    )

    coordinator.handle(_signal())

    assert submission.submitted_live == []
    assert submission.submitted_dry == []
    event_publisher.publish.assert_called_once()
    (published,) = event_publisher.publish.call_args.args
    assert isinstance(published, LiveOrderBlockedEvent)
    assert published.symbol == "BTCUSDT"


def test_exchange_rejection_is_logged_not_raised(caplog) -> None:
    """`BUG-090` — a live order the app's own `notional_check` gate didn't
    catch (margin, rate limit, ...) still reaches the exchange and can come
    back as `OrderRejectedByExchangeError`. Before this fix, nothing in
    this coordinator or its caller (`MarketTickEventHandler.handle()`, no
    `except` of its own) caught it, so one rejected order would crash tick
    processing for the rest of the session."""
    submission = FakeOrderSubmission()
    submission.submit_raises(
        OrderRejectedByExchangeError(
            OrderRejectionReason.INSUFFICIENT_MARGIN, "Margin is insufficient"
        )
    )
    coordinator = _coordinator(submission)

    with caplog.at_level(logging.WARNING):
        coordinator.handle(_signal())  # must not raise

    assert any("rejected" in record.message.lower() for record in caplog.records)


def test_a_network_failure_during_submission_is_logged_not_raised(caplog) -> None:
    """Same worker-boundary reasoning as the rejection case above, for an
    unexpected/network-level failure — this coordinator has no engine
    exception-swallowing wrapper the way UI worker methods do."""
    submission = FakeOrderSubmission()
    submission.submit_raises(ConnectionError("boom"))
    coordinator = _coordinator(submission)

    with caplog.at_level(logging.ERROR):
        coordinator.handle(_signal())  # must not raise

    assert any("boom" in record.message for record in caplog.records)


def test_unknown_symbol_metadata_sends_nothing() -> None:
    submission = FakeOrderSubmission()
    account_reader = Mock()
    account_reader.check_connection.return_value = _status()
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = None
    coordinator = LiveTradingCoordinator(
        "BTCUSDT", submission, account_reader, metadata_provider, Mock(), 20.0, 1.0
    )

    coordinator.handle(_signal())

    assert submission.submitted_live == []
    assert submission.submitted_dry == []
