"""`EPIC-034A` — what the bot chart says reaches the user.

`LiveCandleChart.logged` carries the load's and the stream's messages; the Desk
shows them and the Bots mode never connected it, so a chart that could not
stream said nothing.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
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
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    StreamOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.chart.bot_chart_fixtures import (
    ChartWorld,
    InlineThreadManager,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from .bots_screen_fixtures import stored


def _fakes():
    world = ChartWorld()
    return world.sync, world.history, world.stream, world.market


class _RefusingStream(FakeMarketStream):
    def start(self, owner_id, market_type, symbols, interval) -> StreamOutcome:
        return StreamOutcome(success=False, message="Spot Testnet unreachable.\nHTML")


def test_a_stream_that_cannot_open_is_said_on_the_status_line_and_the_log(
    qapp, caplog
) -> None:
    world = ChartWorld(stream=_RefusingStream())
    heard: list[tuple[str, bool]] = []
    ticks = BotTickFeed(MemoryEventBus(), MarketType.SPOT)
    host = BotChartHost(
        BotChartPorts(
            InlineThreadManager(),
            MarketDataCandleFeed(world.sync, world.history, world.stream, world.market),
            ticks,
        ),
        lambda message, is_error: heard.append((message, is_error)),
    )
    bot = BotSnapshot.of(stored("a00001", BotLifecycleState.RUNNING).bot, None)

    with caplog.at_level(logging.INFO, logger="App.Bots.Chart"):
        host.show(bot)

    assert heard == [("Could not open live stream: Spot Testnet unreachable.", True)]
    assert "Bot a00001 chart: " in caplog.text
    assert "Opening live stream for" in caplog.text
    host.close()


def test_a_failure_with_no_text_still_reaches_the_status_line(qapp) -> None:
    """An exception whose `str()` is empty emits `"[ERROR] "`; the slot must
    not raise on it (the PR #414 review)."""
    heard: list[tuple[str, bool]] = []
    host = BotChartHost(
        BotChartPorts(
            InlineThreadManager(),
            MarketDataCandleFeed(*_fakes()),
            BotTickFeed(MemoryEventBus(), MarketType.SPOT),
        ),
        lambda message, is_error: heard.append((message, is_error)),
    )

    host._on_chart_said("a00001", "[ERROR] ")

    assert heard == [("The chart reported an error.", True)]
