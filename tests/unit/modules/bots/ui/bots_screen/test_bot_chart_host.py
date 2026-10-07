"""`EPIC-034A` — what the bot chart says reaches the user.

`LiveCandleChart.logged` carries the load's and the stream's messages; the Desk
shows them and the Bots mode never connected it, so a chart that could not
stream said nothing. Since `BOT-169` the chart tells the user itself, through
the notifier, on the Bots message bar; the host only logs what it says.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.chart.bot_chart_fixtures import (
    ChartWorld,
    InlineThreadManager,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from .bots_screen_fixtures import stored


class _RefusingStream(FakeMarketStream):
    def start(self, owner_id, market_type, symbols, interval) -> StreamOutcome:
        return StreamOutcome(success=False, message="Spot Testnet unreachable.\nHTML")


def _host(world: ChartWorld, notifier: RecordingNotifier) -> BotChartHost:
    return BotChartHost(
        BotChartPorts(
            InlineThreadManager(),
            lambda _venue: MarketDataCandleFeed(
                world.sync, world.history, world.stream, world.market
            ),
            BotTickFeed(MemoryEventBus(), MarketType.SPOT),
            notifier,
        )
    )


def test_a_stream_that_cannot_open_is_told_on_the_bots_bar_and_logged(
    qapp, caplog
) -> None:
    notifier = RecordingNotifier()
    host = _host(ChartWorld(stream=_RefusingStream()), notifier)
    bot = BotSnapshot.of(stored("a00001", BotLifecycleState.RUNNING).bot, None)

    with caplog.at_level(logging.INFO, logger="App.Bots.Chart"):
        host.show(bot)

    notice = notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert notice.scope == BOTS_ROUTE
    assert notice.retry is not None
    assert "HTML" not in notice.headline
    assert "Bot a00001 chart: " in caplog.text
    assert "Opening live stream for" in caplog.text
    host.close()


def test_a_failure_with_no_text_is_logged_and_does_not_raise(qapp, caplog) -> None:
    """An exception whose `str()` is empty emits `"[ERROR] "`; the slot must
    not raise on it (the PR #414 review)."""
    notifier = RecordingNotifier()
    host = _host(ChartWorld(), notifier)

    with caplog.at_level(logging.WARNING, logger="App.Bots.Chart"):
        host._on_chart_said("a00001", "[ERROR] ")

    assert "Bot a00001 chart: " in caplog.text
    assert notifier.failures == []


_IDS = {TradingVenue.SPOT_MAINNET: "a00002", TradingVenue.SPOT_TESTNET: "a00003"}


def _bot_on(venue: TradingVenue) -> BotSnapshot:
    """A bot's venue never changes, so each venue's bot is a bot of its own."""
    return replace(
        BotSnapshot.of(stored(_IDS[venue], BotLifecycleState.DRAFT).bot, None),
        venue=venue,
    )


def test_a_bots_chart_reads_its_own_venues_feed_and_ticks(qapp) -> None:
    """`BUG-172` — a Spot Mainnet bot charts the mainnet and a Spot Testnet bot the
    testnet: the host asks for the bot's venue's feed and tells the one tick Feed
    to hear that venue only."""
    world = ChartWorld()
    asked: list[TradingVenue] = []
    ticks = BotTickFeed(MemoryEventBus(), MarketType.SPOT)

    def feeds(venue: TradingVenue) -> MarketDataCandleFeed:
        asked.append(venue)
        return MarketDataCandleFeed(
            world.sync, world.history, world.stream, world.market
        )

    host = BotChartHost(
        BotChartPorts(InlineThreadManager(), feeds, ticks, RecordingNotifier())
    )

    host.show(_bot_on(TradingVenue.SPOT_MAINNET))
    assert asked == [TradingVenue.SPOT_MAINNET]
    assert ticks._venue is TradingVenue.SPOT_MAINNET.market_data_venue

    host.show(_bot_on(TradingVenue.SPOT_TESTNET))
    assert asked == [TradingVenue.SPOT_MAINNET, TradingVenue.SPOT_TESTNET]
    assert ticks._venue is TradingVenue.SPOT_TESTNET.market_data_venue

    host.close()
    assert ticks._venue is None
