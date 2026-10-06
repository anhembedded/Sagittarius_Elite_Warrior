"""`BUG-163` — a strategy signal while the trading switch is OFF touches
neither the account (the venue's key) nor the market-metadata endpoint.

Its own file: `test_live_trading_coordinator.py` is over the god-file ceiling
and may not grow (`architecture-rule.md` §5.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def test_a_signal_with_trading_off_reads_no_account_and_no_metadata() -> None:
    """`BUG-163`: arming is allowed only while trading is OFF, so an armed
    strategy evaluating a live tick with the switch off is the normal state —
    and `handle()` used to fetch the symbol metadata and call
    `check_connection()` (an authenticated account read with the venue's key)
    before anything looked at the switch. The refusal is free
    (`ExecuteOrderHandler`'s gate order); the coordinator now asks it first,
    tells the desk why nothing was sent, and touches neither the network nor
    the key."""
    submission = FakeOrderSubmission()
    account_reader = Mock()
    metadata_provider = Mock()
    publisher = Mock()
    off = TradingSessionSnapshot(
        enabled=False,
        orders_sent_this_session=0,
        known_open_symbols=(),
        market_type=None,
        spot_baseline_holdings=None,
    )
    trading_session = Mock()
    trading_session.snapshot.return_value = off
    coordinator = LiveTradingCoordinator(
        "BTCUSDT",
        submission,
        account_reader,
        metadata_provider,
        publisher,
        trading_session,
        20.0,
        1.0,
        venue=TradingVenue.FUTURES_TESTNET,
    )
    signal = Signal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        reason="test",
        price=64000.0,
        time=datetime(2026, 10, 6, tzinfo=UTC),
    )

    coordinator.handle(signal)

    account_reader.check_connection.assert_not_called()
    metadata_provider.get_or_fetch.assert_not_called()
    assert submission.submitted_live == []
    (published,) = (call.args[0] for call in publisher.publish.call_args_list)
    assert isinstance(published, LiveOrderBlockedEvent)
    assert published.symbol == "BTCUSDT"
    assert "Trading is OFF" in published.reason
