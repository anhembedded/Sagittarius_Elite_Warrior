"""`EPIC-029G` — a bot's chart: one drawer for the three surfaces, history
and a stream through the shared live chart, ticks through the bots' Feed.

@details Real `ChartCard`, `BotChart`, `BotTickFeed` and engine
`MemoryEventBus`; the market-data ports are their verified fakes behind the
real `MarketDataCandleFeed`.
"""

from __future__ import annotations

from dataclasses import replace

import pyqtgraph as pg
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bot_tick_feed import BotTickFeed
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_overlay_drawer import (
    FILLS_KEY,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.overlay_items import (
    overlay_items,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.chart.bot_chart_fixtures import (
    ChartWorld,
    build_chart,
    sample_overlay,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)


def _drawn(card: ChartCard) -> list[tuple[float, str, str]]:
    """What the card's price plot shows of the bot: each labelled horizontal
    line's price, label and colour, lowest first. The card's own last-price
    line is left out: its label is a format string (`{value:.4f}`), which no
    overlay label is."""
    lines = [
        item
        for item in card.plot_layout.main_plot.items
        if isinstance(item, pg.InfiniteLine)
        and item.angle == 0
        and hasattr(item, "label")
        and "{" not in item.label.format
    ]
    return sorted(
        (line.value(), line.label.format, line.pen.color().name()) for line in lines
    )


def _bands(card: ChartCard) -> list[tuple[float, float]]:
    return sorted(
        tuple(item.getRegion())
        for item in card.plot_layout.main_plot.items
        if isinstance(item, pg.LinearRegionItem)
    )


def test_the_three_surfaces_draw_identical_items_for_one_overlay(qapp) -> None:
    """The planner preview reads stored history, the backtest draws the
    candles it ran over, the running bot goes live: each draws the overlay
    through the same drawer, so the items match one for one."""
    overlay = sample_overlay()
    world = ChartWorld()
    world.history.seed([candle("BTCUSDT", minute) for minute in range(5)])

    preview, preview_card = build_chart(world)
    preview.show_symbol("BTCUSDT")
    backtest, backtest_card = build_chart()
    backtest.draw_history([candle("BTCUSDT", minute) for minute in range(5)])
    live, live_card = build_chart()
    live.show_symbol("BTCUSDT")
    live.follow(BotTickFeed(MemoryEventBus(), MarketType.SPOT, parent=live_card))

    drawn = [chart.show_overlay(overlay) for chart in (preview, backtest, live)]

    assert drawn[0] == drawn[1] == drawn[2] == overlay_items(overlay)
    on_cards = [_drawn(card) for card in (preview_card, backtest_card, live_card)]
    assert on_cards[0] == on_cards[1] == on_cards[2]
    assert len(on_cards[0]) == len(overlay.lines)
    bands = [_bands(card) for card in (preview_card, backtest_card, live_card)]
    assert bands[0] == bands[1] == bands[2] == [(60000.0, 62500.0), (67500.0, 70000.0)]


def test_each_role_draws_in_its_own_colour(qapp) -> None:
    items = overlay_items(sample_overlay())
    by_label = {level.label: level.color for level in items.levels}

    assert by_label["L3"] != by_label["L6"]  # a resting buy against a resting sell
    assert by_label["L7"] not in {by_label["L3"], by_label["L6"]}  # partial
    assert by_label["SL"] != by_label["TP"]


def test_a_new_overlay_replaces_the_old_one(qapp) -> None:
    chart, card = build_chart()
    chart.show_overlay(sample_overlay())

    chart.show_overlay(BotOverlay())

    assert _drawn(card) == []
    assert _bands(card) == []


def test_the_fills_are_marked_where_and_when_they_traded(qapp, monkeypatch) -> None:
    chart, card = build_chart()
    marked: list[tuple[str, list]] = []
    monkeypatch.setattr(
        card, "set_script_markers", lambda key, markers: marked.append((key, markers))
    )

    chart.show_overlay(sample_overlay())

    ((key, markers),) = marked
    assert key == FILLS_KEY
    assert [
        (price, label, direction) for _t, price, label, _c, direction in markers
    ] == [
        (64000.0, "L4", "up"),
        (65000.0, "L5", "down"),
    ]


def test_the_planner_preview_never_goes_on_the_network(qapp) -> None:
    """`BUG-107`: showing a bot's chart reads stored history only."""
    world = ChartWorld()

    chart, _card = build_chart(world)
    chart.show_symbol("BTCUSDT")

    assert world.sync.requests == []
    assert world.stream.calls == []


def test_a_running_bot_streams_under_its_own_owner(qapp) -> None:
    """`BOT-126`: the bot's chart holds its own subscription, `bot.<id>`,
    and releasing it leaves a desk's on the same symbol alone."""
    world = ChartWorld()
    world.stream.start(
        "desk.spot_testnet", MarketType.SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE
    )
    chart, card = build_chart(world)
    chart.show_symbol("BTCUSDT")

    chart.follow(BotTickFeed(MemoryEventBus(), MarketType.SPOT, parent=card))

    assert world.sync.was_asked_for("BTCUSDT", TimeFrame.ONE_MINUTE)
    held = world.stream.held_by("bot.a3f9c1")
    assert held is not None
    assert held.market_type is MarketType.SPOT
    chart.shutdown()
    assert world.stream.held_by("bot.a3f9c1") is None
    assert world.stream.held_by("desk.spot_testnet") is not None


def test_only_its_markets_candle_at_its_interval_reaches_the_chart(
    qapp, monkeypatch
) -> None:
    bus = MemoryEventBus()
    chart, card = build_chart()
    chart.show_symbol("BTCUSDT")
    chart.follow(BotTickFeed(bus, MarketType.SPOT, parent=card))
    appended: list[float] = []
    monkeypatch.setattr(
        card, "append_closed_candle", lambda t, *_ohlc: appended.append(t)
    )

    bus.emit(
        MarketTickEvent(
            market_data=candle("BTCUSDT", 9), market_type=MarketType.FUTURES_USD_M
        )
    )
    bus.emit(
        MarketTickEvent(market_data=candle("ETHUSDT", 9), market_type=MarketType.SPOT)
    )
    bus.emit(
        MarketTickEvent(
            market_data=candle("BTCUSDT", 9, interval=TimeFrame.FIVE_MINUTES),
            market_type=MarketType.SPOT,
        )
    )
    qapp.processEvents()
    assert appended == []

    tick = candle("BTCUSDT", 9)
    bus.emit(MarketTickEvent(market_data=tick, market_type=MarketType.SPOT))
    qapp.processEvents()
    assert appended == [tick.close_time.timestamp()]


def test_a_candle_still_forming_updates_the_last_bar(qapp, monkeypatch) -> None:
    bus = MemoryEventBus()
    chart, card = build_chart()
    chart.show_symbol("BTCUSDT")
    chart.follow(BotTickFeed(bus, MarketType.SPOT, parent=card))
    updated: list[float] = []
    monkeypatch.setattr(card, "update_last_candle", lambda t, *_ohlc: updated.append(t))

    forming = replace(candle("BTCUSDT", 9, closed=False), is_closed=False)
    bus.emit(MarketTickEvent(market_data=forming, market_type=MarketType.SPOT))
    qapp.processEvents()

    assert updated == [forming.close_time.timestamp()]


def test_after_shutdown_a_shown_symbol_opens_no_stream(qapp) -> None:
    """The PR #321 review: a released chart is quiet again, so a symbol
    shown afterwards reads history only."""
    world = ChartWorld()
    chart, card = build_chart(world)
    chart.show_symbol("BTCUSDT")
    chart.follow(BotTickFeed(MemoryEventBus(), MarketType.SPOT, parent=card))
    chart.shutdown()
    syncs = len(world.sync.requests)

    chart.show_symbol("ETHUSDT")

    assert chart.is_live is False
    assert len(world.sync.requests) == syncs
    assert world.stream.held_by("bot.a3f9c1") is None
