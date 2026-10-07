"""Builders for the bot chart's tests: a real `ChartCard` and `BotChart`, the
market-data ports' verified fakes behind the real `MarketDataCandleFeed`, and
the report's example Grid overlay."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    BotOverlay,
    FillSide,
    OverlayFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    GridActivity,
    GridOverlaySource,
    LevelState,
    grid_overlay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_chart import BotChart
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_stream_owner import (
    bot_stream_owner,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

BOT = BotId("a3f9c1")


class InlineThreadManager(IThreadManager):
    """Runs each task at once on the test's thread."""

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


@dataclass
class ChartWorld:
    """The fakes behind one bot chart."""

    sync: FakeMarketDataSync = field(default_factory=FakeMarketDataSync)
    history: FakeHistoricalKlines = field(default_factory=FakeHistoricalKlines)
    stream: FakeMarketStream = field(default_factory=FakeMarketStream)
    market: MarketType = MarketType.SPOT
    notifier: RecordingNotifier = field(default_factory=RecordingNotifier)


def build_chart(world: ChartWorld | None = None) -> tuple[BotChart, ChartCard]:
    world = world or ChartWorld()
    card = ChartCard("BTCUSDT")
    ports = LiveChartPorts(
        thread_manager=InlineThreadManager(),
        feed=MarketDataCandleFeed(
            world.sync, world.history, world.stream, world.market
        ),
        stream_owner=bot_stream_owner(BOT),
        interval="1m",
        market=world.market,
        notifier=world.notifier,
        scope=BOTS_ROUTE,
    )
    return BotChart(card, ports, parent=card), card


def sample_overlay() -> BotOverlay:
    """The report's example Grid, run for a while: two levels changed state,
    two fills and an average cost, with the ATR zones."""
    evaluation = evaluate_grid(inputs(daily_atr=Decimal(2500)), GridThresholds())
    assert evaluation.params is not None and evaluation.plan is not None
    activity = GridActivity(
        level_states={4: LevelState.RESTING_SELL, 7: LevelState.PARTIAL},
        fills=(
            OverlayFill(
                datetime(2026, 10, 4, 9, tzinfo=UTC), Decimal(64000), FillSide.BUY, "L4"
            ),
            OverlayFill(
                datetime(2026, 10, 4, 12, tzinfo=UTC),
                Decimal(65000),
                FillSide.SELL,
                "L5",
            ),
        ),
        average_cost=Decimal(64000),
    )
    return grid_overlay(
        GridOverlaySource(
            evaluation.params,
            evaluation.plan,
            GridThresholds(),
            activity=activity,
            daily_atr=Decimal(2500),
        )
    )
