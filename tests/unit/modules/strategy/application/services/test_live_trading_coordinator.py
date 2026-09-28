from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_trading_coordinator import (
    LiveTradingCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def _metadata() -> SymbolOrderMetadata:
    return SymbolOrderMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _status(
    usdt_balance: Decimal | None = Decimal(1000),
    holdings: tuple[SpotHolding, ...] | None = None,
) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=usdt_balance,
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=0,
        holdings=holdings,
    )


def _snapshot(
    market_type: MarketType | None = None,
    spot_baseline_holdings: dict[str, Decimal] | None = None,
) -> TradingSessionSnapshot:
    return TradingSessionSnapshot(
        enabled=True,
        orders_sent_this_session=0,
        known_open_symbols=(),
        market_type=market_type,
        spot_baseline_holdings=spot_baseline_holdings,
    )


def _trading_session(snapshot: TradingSessionSnapshot | None = None) -> Mock:
    session = Mock()
    session.snapshot.return_value = snapshot if snapshot is not None else _snapshot()
    return session


def _coordinator(
    submission: FakeOrderSubmission,
    live_symbol: str = "BTCUSDT",
    event_publisher: Mock | None = None,
    trading_session: Mock | None = None,
    sizing_percent: float = 20.0,
    leverage: float = 1.0,
    account_reader: Mock | None = None,
) -> LiveTradingCoordinator:
    if account_reader is None:
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
        trading_session if trading_session is not None else _trading_session(),
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
        "BTCUSDT",
        submission,
        account_reader,
        metadata_provider,
        Mock(),
        _trading_session(),
        20.0,
        1.0,
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
        _trading_session(),
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
        "BTCUSDT",
        submission,
        account_reader,
        metadata_provider,
        Mock(),
        _trading_session(),
        20.0,
        1.0,
    )

    coordinator.handle(_signal())

    assert submission.submitted_live == []
    assert submission.submitted_dry == []


# --------------------------------------------------------------------- #
# Spot SELL sizing (`EPIC-027N` AC4)
# --------------------------------------------------------------------- #


def _btc_holding(total: Decimal) -> SpotHolding:
    return SpotHolding(
        asset="BTC", free=total, locked=Decimal(0), dust_threshold=Decimal("0.0001")
    )


def test_spot_sell_sizes_from_the_actual_holding_not_a_percent_of_balance() -> None:
    """AC4 — SELL on Spot must size from what is actually held, floored to
    the lot step; the pre-existing percent-of-balance formula (`sizing=20%`
    here, which would size against the 1000 USDT balance instead) must
    never be reached for this branch."""
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))
    account_reader = Mock()
    account_reader.check_connection.return_value = _status(
        holdings=(_btc_holding(Decimal("0.05")),)
    )
    snapshot = _snapshot(
        market_type=MarketType.SPOT, spot_baseline_holdings={"BTC": Decimal("0.02")}
    )
    coordinator = _coordinator(
        submission,
        account_reader=account_reader,
        trading_session=_trading_session(snapshot),
    )

    coordinator.handle(_signal(action=SignalAction.SELL))

    (request,) = submission.submitted_live
    assert request.side is OrderSide.SELL
    assert request.quantity == Decimal("0.03")


def test_spot_sell_never_sells_below_the_baseline() -> None:
    """The same never-sell-the-baseline rule `EPIC-027M` established for
    Emergency Stop, applied to the strategy's own exit signal: holding
    exactly the baseline sends nothing."""
    submission = FakeOrderSubmission()
    account_reader = Mock()
    account_reader.check_connection.return_value = _status(
        holdings=(_btc_holding(Decimal("0.02")),)
    )
    snapshot = _snapshot(
        market_type=MarketType.SPOT, spot_baseline_holdings={"BTC": Decimal("0.02")}
    )
    coordinator = _coordinator(
        submission,
        account_reader=account_reader,
        trading_session=_trading_session(snapshot),
    )

    coordinator.handle(_signal(action=SignalAction.SELL))

    assert submission.submitted_live == []
    assert submission.submitted_dry == []


def test_spot_sell_refuses_with_no_baseline_recorded() -> None:
    """`None` (never enabled this session on Spot, or a non-Spot enable) is
    the unrecoverable-unknown case: sell nothing rather than guess a
    baseline of zero and offer up the user's entire pre-existing holding."""
    submission = FakeOrderSubmission()
    account_reader = Mock()
    account_reader.check_connection.return_value = _status(
        holdings=(_btc_holding(Decimal("0.05")),)
    )
    event_publisher = Mock()
    snapshot = _snapshot(market_type=MarketType.SPOT, spot_baseline_holdings=None)
    coordinator = _coordinator(
        submission,
        event_publisher=event_publisher,
        account_reader=account_reader,
        trading_session=_trading_session(snapshot),
    )

    coordinator.handle(_signal(action=SignalAction.SELL))

    assert submission.submitted_live == []
    assert submission.submitted_dry == []
    event_publisher.publish.assert_called_once()
    (published,) = event_publisher.publish.call_args.args
    assert isinstance(published, LiveOrderBlockedEvent)


def test_spot_sell_surplus_smaller_than_one_lot_step_sends_nothing() -> None:
    """A real surplus below the exchange's own lot step floors to dust,
    reported as a blocked event rather than a fractional order."""
    submission = FakeOrderSubmission()
    account_reader = Mock()
    account_reader.check_connection.return_value = _status(
        holdings=(_btc_holding(Decimal("0.0205")),)
    )
    event_publisher = Mock()
    snapshot = _snapshot(
        market_type=MarketType.SPOT, spot_baseline_holdings={"BTC": Decimal("0.02")}
    )
    coordinator = _coordinator(
        submission,
        event_publisher=event_publisher,
        account_reader=account_reader,
        trading_session=_trading_session(snapshot),
    )

    coordinator.handle(_signal(action=SignalAction.SELL))

    assert submission.submitted_live == []
    event_publisher.publish.assert_called_once()


def test_spot_buy_still_uses_percent_of_balance_sizing() -> None:
    """The Spot branch only applies to SELL — BUY keeps the existing
    quote-balance sizing unchanged, since `usdt_balance` is already the
    Spot quote balance (`EPIC-027H`)."""
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))
    snapshot = _snapshot(market_type=MarketType.SPOT, spot_baseline_holdings={})
    coordinator = _coordinator(submission, trading_session=_trading_session(snapshot))

    coordinator.handle(_signal(action=SignalAction.BUY))

    (request,) = submission.submitted_live
    assert request.side is OrderSide.BUY
    assert request.quantity > 0
