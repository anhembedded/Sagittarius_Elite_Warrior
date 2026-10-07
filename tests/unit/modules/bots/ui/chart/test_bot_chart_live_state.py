"""`EPIC-034G`, D9 — a draft bot's chart can go live as a view-only price
stream; a chart at rest draws no live candle."""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bot_tick_feed import BotTickFeed
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_chart_host import (
    BotChartHost,
    BotChartPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    COMMAND_PREFIX,
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    chart_command_id,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    LiveChartCommand,
    LiveChartEvent,
    LiveChartState,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_stream_command import (
    LIVE_STREAM,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.chart.bot_chart_fixtures import (
    ChartWorld,
    InlineThreadManager,
)
from Sagittarius_Elite_Warrior.tests.unit.support.charting.live_chart.live_chart_fixtures import (
    ScriptedCandleFeed,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

S = LiveChartState


def _tick(bus: MemoryEventBus, minute: int = 9) -> None:
    bus.emit(
        MarketTickEvent(
            market_data=candle("BTCUSDT", minute, interval=TimeFrame.ONE_HOUR),
            market_type=MarketType.SPOT,
            market_data_venue=MarketDataVenue.SPOT_TESTNET,
        )
    )


def _bot(state: BotLifecycleState) -> BotSnapshot:
    return BotSnapshot(
        "a3f9c1",
        "g",
        "grid",
        TradingVenue.SPOT_TESTNET,
        "BTCUSDT",
        state,
        datetime(2026, 10, 7, tzinfo=UTC),
        None,
    )


def _host(world: ChartWorld, bus: MemoryEventBus) -> BotChartHost:
    return BotChartHost(
        BotChartPorts(
            thread_manager=InlineThreadManager(),
            feeds=lambda _venue: MarketDataCandleFeed(
                world.sync, world.history, world.stream, world.market
            ),
            ticks=BotTickFeed(bus, MarketType.SPOT),
            notifier=RecordingNotifier(),
        ),
    )


def test_a_draft_chart_goes_live_by_the_users_command_and_draws_what_streams(
    qapp, monkeypatch
) -> None:
    world, bus = ChartWorld(), MemoryEventBus()
    host = _host(world, bus)
    card = host.show(_bot(BotLifecycleState.DRAFT))
    assert isinstance(card, ChartCard)
    chart = host._chart
    assert chart is not None and chart.live_state is S.HISTORY
    assert world.stream.held_by("bot.a3f9c1") is None
    appended: list[float] = []
    monkeypatch.setattr(
        card, "append_closed_candle", lambda t, *_ohlc: appended.append(t)
    )
    _tick(bus)
    qapp.processEvents()
    assert appended == [], "a chart at rest draws no live candle"

    chart.run_command(LiveChartCommand.GO_LIVE)
    _tick(bus)
    qapp.processEvents()

    assert chart.live_state is S.LIVE
    held = world.stream.held_by("bot.a3f9c1")
    assert held is not None and held.market_type is MarketType.SPOT
    assert appended == [
        candle("BTCUSDT", 9, interval=TimeFrame.ONE_HOUR).close_time.timestamp()
    ]
    host.close()


def test_stopping_a_drafts_live_stream_releases_only_its_own_owner(qapp) -> None:
    world, bus = ChartWorld(), MemoryEventBus()
    host = _host(world, bus)
    host.show(_bot(BotLifecycleState.DRAFT))
    chart = host._chart
    assert chart is not None
    chart.run_command(LiveChartCommand.GO_LIVE)

    chart.run_command(LiveChartCommand.STOP_LIVE)

    assert chart.live_state is S.HISTORY
    assert world.stream.held_by("bot.a3f9c1") is None
    host.close()


def test_a_running_bots_chart_is_live_on_its_own(qapp) -> None:
    world, bus = ChartWorld(), MemoryEventBus()
    host = _host(world, bus)

    host.show(_bot(BotLifecycleState.RUNNING))

    assert host._chart is not None and host._chart.live_state is S.LIVE
    assert world.stream.held_by("bot.a3f9c1") is not None
    host.close()


def test_a_draft_that_starts_while_live_stays_live_with_one_stream(qapp) -> None:
    world, bus = ChartWorld(), MemoryEventBus()
    host = _host(world, bus)
    host.show(_bot(BotLifecycleState.DRAFT))
    chart = host._chart
    assert chart is not None
    chart.run_command(LiveChartCommand.GO_LIVE)

    host.show(_bot(BotLifecycleState.RUNNING))

    assert host._chart is chart and chart.live_state is S.LIVE
    assert [call for call in world.stream.calls if call[0] == "start"] == [
        ("start", "bot.a3f9c1")
    ]
    host.close()


def test_a_chart_that_is_connecting_already_draws_what_streams(
    qapp, monkeypatch
) -> None:
    """The History gate is only for rest: once a stream is asked for, its
    candles draw (the reviewer's gap in the first round)."""
    world, bus = ChartWorld(), MemoryEventBus()
    host = _host(world, bus)
    card = host.show(_bot(BotLifecycleState.DRAFT))
    chart = host._chart
    assert chart is not None and card is not None
    chart._dispatch(LiveChartEvent.GO_LIVE_REQUESTED)
    appended: list[float] = []
    monkeypatch.setattr(
        card, "append_closed_candle", lambda t, *_ohlc: appended.append(t)
    )

    _tick(bus)
    qapp.processEvents()

    assert chart.live_state is S.CONNECTING
    assert len(appended) == 1
    host.close()


def test_the_live_stream_command_follows_the_selected_bots_chart(qapp) -> None:
    owner = QObject()
    world, bus = ChartWorld(), MemoryEventBus()
    host = _host(world, bus)
    registry = bound_actions(owner, bots_commands("bots"), host.bind_commands)
    command = registry.action(chart_command_id(COMMAND_PREFIX, LIVE_STREAM))
    assert not command.isEnabled()

    host.show(_bot(BotLifecycleState.DRAFT))
    assert command.isEnabled() and not command.isChecked()
    command.trigger()
    assert host._chart is not None and host._chart.live_state is S.LIVE
    assert command.isChecked()
    assert world.stream.held_by("bot.a3f9c1") is not None

    host.close()
    assert not command.isEnabled()
    owner.deleteLater()


def test_the_error_state_carries_the_message_the_status_line_shows(qapp) -> None:
    """`EPIC-034A` connected the chart's `logged` lines to the status line;
    the Error state is the same failure, in words on the chip."""
    feed = ScriptedCandleFeed()
    feed.stream_message = "exchange said no"
    notifier = RecordingNotifier()
    host = BotChartHost(
        BotChartPorts(
            thread_manager=InlineThreadManager(),
            feeds=lambda _venue: feed,
            ticks=BotTickFeed(MemoryEventBus(), MarketType.SPOT),
            notifier=notifier,
        ),
    )
    host.show(_bot(BotLifecycleState.DRAFT))
    chart = host._chart
    assert chart is not None

    chart.run_command(LiveChartCommand.GO_LIVE)

    assert chart.live_state is S.ERROR
    assert "exchange said no" not in chart.live_error
    assert notifier.last.detail == "exchange said no"
    host.close()
