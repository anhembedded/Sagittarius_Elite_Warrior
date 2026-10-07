"""`BUG-172` — a kind's backtest page is built for the bot's kind **and venue**.

@details Its chart and its sync read the market the bot's orders fill in, so two
Grid bots on two venues must not share a page (and so a sync): selecting a bot of
the other venue builds that venue's page, and selecting one of the same venue and
kind keeps the page it has.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.kind_backtests import (
    KindBacktests,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_backtest import (
    BacktestPorts,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.chart.bot_chart_fixtures import (
    InlineThreadManager,
)

from .bots_screen_fixtures import stored

_TESTNET = TradingVenue.SPOT_TESTNET
_MAINNET = TradingVenue.SPOT_MAINNET


def _bot(bot_id: str, venue: TradingVenue) -> SimpleNamespace:
    snapshot = replace(
        BotSnapshot.of(stored(bot_id, BotLifecycleState.DRAFT).bot, None), venue=venue
    )
    return SimpleNamespace(bot=snapshot, edited=None, market=None)


def test_a_page_is_built_per_venue_and_kept_for_the_same_venue(qapp) -> None:
    sources = FakeMarketDataSources()
    for venue in (_TESTNET, _MAINNET):
        sources.serving(FakeMarketDataSources.ports(venue.market_data_venue))
    built: list[TradingVenue] = []

    def ports_for(venue: TradingVenue) -> BacktestPorts:
        built.append(venue)
        ports = sources.ports_for(venue.market_data_venue)
        return BacktestPorts(
            InlineThreadManager(),
            SimpleNamespace(dispatch=lambda *_a, **_k: None),  # type: ignore[arg-type]
            ports.sync,
            MarketDataCandleFeed(
                ports.sync, ports.history, ports.stream, MarketType.SPOT
            ),
            RecordingNotifier(),
        )

    pages: list[object] = []
    backtests = KindBacktests(ports_for, pages.append)

    backtests.follow(_bot("a00001", _TESTNET))  # type: ignore[arg-type]
    backtests.follow(_bot("a00002", _TESTNET))  # type: ignore[arg-type]
    assert built == [_TESTNET]

    backtests.follow(_bot("a00003", _MAINNET))  # type: ignore[arg-type]
    assert built == [_TESTNET, _MAINNET]
    assert len(pages) == 2 and pages[0] is not pages[1]

    backtests.close()
