"""`EPIC-029F` — the selected bot's chart, built per bot.

A chart's stream owner is the bot's own (`bot.<id>`, `bot_stream_owner`), so
selecting another bot shuts the previous chart down (releasing its stream)
and builds a new one. A bot at rest (DRAFT, STOPPED) shows its stored candles
only, no network (`BUG-107`: opening a screen never starts a stream by
itself); a bot with a run follows live candles through the module's one
`BotTickFeed`. Everything is drawn through `BotChart.show_overlay`, never a
drawer of this screen's own (the PR 321 review).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bot_tick_feed import BotTickFeed
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_chart import BotChart
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_stream_owner import (
    bot_stream_owner,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

#: The timeframe a bot's chart opens on; the chart's own picker changes it.
BOT_CHART_INTERVAL = "1h"

_AT_REST = frozenset({BotLifecycleState.DRAFT, BotLifecycleState.STOPPED})


@dataclass(frozen=True)
class BotChartPorts:
    """What every bot chart is built from."""

    thread_manager: IThreadManager
    #: The Spot candles (a Grid is a Spot kind): `MarketDataCandleFeed`.
    feed: ICandleFeed
    ticks: BotTickFeed
    market: MarketType = MarketType.SPOT


class BotChartHost:
    """@brief Owns the selected bot's `BotChart`, one at a time."""

    def __init__(self, ports: BotChartPorts) -> None:
        self._ports = ports
        self._chart: BotChart | None = None
        self._card: ChartCard | None = None
        self._bot_id: str | None = None

    def show(self, bot: BotSnapshot | None) -> QWidget | None:
        """The chart for `bot`, built anew when the bot differs; `None` for no bot."""
        if bot is not None and bot.bot_id == self._bot_id and self._card is not None:
            self._follow_if_live(bot)
            return self._card
        self.close()
        if bot is None:
            return None
        card = ChartCard(bot.symbol)
        chart = BotChart(
            card,
            LiveChartPorts(
                thread_manager=self._ports.thread_manager,
                feed=self._ports.feed,
                stream_owner=bot_stream_owner(BotId(bot.bot_id)),
                interval=BOT_CHART_INTERVAL,
                market=self._ports.market,
            ),
            parent=card,
        )
        chart.show_symbol(bot.symbol)
        self._card, self._chart, self._bot_id = card, chart, bot.bot_id
        self._follow_if_live(bot)
        return card

    def draw(self, overlay: BotOverlay | None) -> None:
        if self._chart is not None:
            self._chart.show_overlay(overlay or BotOverlay())

    def fit_levels(self) -> bool:
        return self._chart.fit_levels() if self._chart is not None else False

    def close(self) -> None:
        """Releases the chart's stream and its load in flight. Safe to call twice."""
        if self._chart is not None:
            self._chart.shutdown()
        if self._card is not None:
            self._card.cleanup()
            self._card.deleteLater()
        self._chart = self._card = None
        self._bot_id = None

    def _follow_if_live(self, bot: BotSnapshot) -> None:
        if self._chart is not None and bot.state not in _AT_REST:
            self._chart.follow(self._ports.ticks)
