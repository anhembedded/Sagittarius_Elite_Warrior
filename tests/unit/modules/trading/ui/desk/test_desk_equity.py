"""`EPIC-028M` — `DeskEquity`: a desk's equity chart, the backlog first and
then each sample, carried from the single Trading screen when it left
(`EPIC-021M`, `BUG-100`).

@details The chart is the real `ChartCard`, subclassed only to record what it
was asked to draw; the curve is the verified `FakeEquityCurve`; the feed is the
real `EquityFeed` on the engine's `MemoryEventBus`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_equity_curve import (
    FakeEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_equity import (
    DeskEquity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_chart_adapter import (
    equity_sample_to_candle,
    equity_samples_to_candles,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_feed import EquityFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

FUTURES = TradingVenue.FUTURES_TESTNET


class RecordingChart(ChartCard):
    """The real chart, recording what it was asked to draw."""

    def __init__(self) -> None:
        super().__init__("Equity")
        self.seeded: list[list] = []
        self.appended: list[tuple] = []

    def render_historical_data(self, data: list) -> None:
        self.seeded.append(list(data))
        super().render_historical_data(data)

    def append_closed_candle(self, *candle: float) -> None:
        self.appended.append(candle)
        super().append_closed_candle(*candle)


class CurveSampledWhileRead(FakeEquityCurve):
    """A sample recorded while the backlog is read: the moment `BUG-100`
    lost it, because the chart subscribed after reading."""

    def __init__(self, feed: EquityFeed, late: EquitySample) -> None:
        super().__init__()
        self._feed = feed
        self._late = late

    def samples(self) -> tuple[EquitySample, ...]:
        backlog = super().samples()
        self._feed.equitySampled.emit(
            EquitySampledEvent(sample=self._late, venue=FUTURES)
        )
        return backlog


def _sample(minute: int) -> EquitySample:
    return EquitySample(
        captured_at=datetime(2026, 10, 2, 9, 0, tzinfo=UTC) + timedelta(minutes=minute),
        wallet_balance=Decimal(1000 + minute),
        unrealized_pnl=Decimal(0),
    )


def test_the_backlog_is_drawn_when_the_desk_opens(qtbot) -> None:
    chart, curve = RecordingChart(), FakeEquityCurve()
    qtbot.addWidget(chart)
    curve.seed([_sample(0), _sample(1)])

    DeskEquity(chart, curve, EquityFeed(MemoryEventBus(), FUTURES))

    assert chart.seeded == [equity_samples_to_candles([_sample(0), _sample(1)])]


def test_each_sample_of_the_venue_appends_one_point(qtbot, qapp) -> None:
    chart, bus = RecordingChart(), MemoryEventBus()
    qtbot.addWidget(chart)
    feed = EquityFeed(bus, FUTURES, parent=chart)  # the desk parents its feeds
    DeskEquity(chart, FakeEquityCurve(), feed, parent=chart)

    bus.emit(EquitySampledEvent(sample=_sample(5), venue=FUTURES))
    bus.emit(EquitySampledEvent(sample=_sample(6), venue=TradingVenue.SPOT_TESTNET))
    qapp.processEvents()

    assert chart.appended == [equity_sample_to_candle(_sample(5))]


def test_a_sample_recorded_while_the_backlog_is_read_is_drawn(qtbot) -> None:
    """`BUG-100` — subscribe, then read: the other order loses this sample
    until the desk is opened again."""
    chart = RecordingChart()
    qtbot.addWidget(chart)
    feed = EquityFeed(MemoryEventBus(), FUTURES)

    DeskEquity(chart, CurveSampledWhileRead(feed, _sample(7)), feed)

    assert chart.appended == [equity_sample_to_candle(_sample(7))]
