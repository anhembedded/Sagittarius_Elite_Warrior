"""`EPIC-028C` — a screen's feeds forward only the venue it shows;
`EPIC-028K` — a desk's follow the venue it is built for, signals included.

@details The bus is the real `MemoryEventBus`. The screen sees only its
venue's equity and fills.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui import screen_venue_feeds
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_SAMPLE = EquitySample(
    captured_at=datetime(2026, 9, 29, tzinfo=UTC),
    wallet_balance=Decimal(1000),
    unrealized_pnl=Decimal(0),
)


def test_a_screens_feeds_forward_only_the_venue_it_shows(qapp) -> None:
    bus = MemoryEventBus()
    parent = QObject()
    feeds = screen_venue_feeds.build_for(bus, TradingVenue.SPOT_TESTNET, parent)
    equity: list = []
    closed: list = []
    feeds.equity.equitySampled.connect(equity.append)
    feeds.orders.positionClosed.connect(closed.append)

    bus.emit(EquitySampledEvent(sample=_SAMPLE, venue=TradingVenue.FUTURES_TESTNET))
    bus.emit(EquitySampledEvent(sample=_SAMPLE, venue=TradingVenue.SPOT_TESTNET))
    bus.emit(PositionClosedEvent(symbol="BTCUSDT", venue=TradingVenue.FUTURES_TESTNET))
    qapp.processEvents()

    assert [event.venue for event in equity] == [TradingVenue.SPOT_TESTNET]
    assert closed == []


def _signal(symbol: str) -> Signal:
    return Signal(
        symbol=symbol,
        action=SignalAction.BUY,
        reason="test",
        price=100.0,
        time=datetime(2026, 9, 29, tzinfo=UTC),
    )


def test_a_desks_signals_are_its_own_venues_and_never_a_backtests(qapp) -> None:
    """`EPIC-028K` — two desks share one bus. The Futures desk's strategy card
    must not show Spot's signal, and neither desk shows a backtest's
    (`venue=None`), which used to need each presenter's own symbol filter."""
    bus = MemoryEventBus()
    parent = QObject()
    futures = screen_venue_feeds.build_for(bus, TradingVenue.FUTURES_TESTNET, parent)
    spot = screen_venue_feeds.build_for(bus, TradingVenue.SPOT_TESTNET, parent)
    heard: dict[str, list] = {"futures": [], "spot": []}
    futures.signals.signalGenerated.connect(heard["futures"].append)
    spot.signals.signalGenerated.connect(heard["spot"].append)

    bus.emit(
        SignalGeneratedEvent(
            signal=_signal("BTCUSDT"), venue=TradingVenue.FUTURES_TESTNET
        )
    )
    bus.emit(
        SignalGeneratedEvent(signal=_signal("ETHUSDT"), venue=TradingVenue.SPOT_TESTNET)
    )
    bus.emit(SignalGeneratedEvent(signal=_signal("BTCUSDT")))
    qapp.processEvents()

    assert [e.signal.symbol for e in heard["futures"]] == ["BTCUSDT"]
    assert [e.signal.symbol for e in heard["spot"]] == ["ETHUSDT"]
