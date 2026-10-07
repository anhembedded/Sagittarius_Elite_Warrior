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

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

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
from Sagittarius_Elite_Warrior.src.support.charting.live_stream_mirror import (
    LiveStreamMirror,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .bots_commands import COMMAND_PREFIX

#: The timeframe a bot's chart opens on; the chart's own picker changes it.
BOT_CHART_INTERVAL = "1h"

#: What `LiveCandleChart.logged` puts before a failure.
_ERROR_TAG = "[ERROR]"
_MAX_STATUS_CHARS = 200
#: A failure whose text is empty still shows on the status line.
_UNSAID_FAILURE = "The chart reported an error."

logger = logging.getLogger("App.Bots.Chart")

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

    def __init__(
        self, ports: BotChartPorts, show_status: Callable[[str, bool], None]
    ) -> None:
        self._ports = ports
        self._show_status = show_status
        self._chart: BotChart | None = None
        self._card: ChartCard | None = None
        self._bot_id: str | None = None
        self._live_stream = LiveStreamMirror(COMMAND_PREFIX)

    def bind_commands(self, binder: ICommandBinder) -> None:
        """Binds Live stream, which follows the selected bot's chart."""
        self._live_stream.bind_commands(binder)
        self._live_stream.follow_chart(self._chart)

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
        chart.attach_ticks(self._ports.ticks)
        chart.logged.connect(partial(self._on_chart_said, bot.bot_id))
        chart.show_symbol(bot.symbol)
        self._card, self._chart, self._bot_id = card, chart, bot.bot_id
        self._live_stream.follow_chart(chart)
        self._follow_if_live(bot)
        return card

    def _on_chart_said(self, bot_id: str, text: str) -> None:
        """What the chart's load and stream say, the way the Desk shows its
        chart's (`EPIC-034A`): on the bot's log tab, through the `App.Bots`
        log feed, and a failure on the status line too. The text may carry an
        exchange's answer, so the status line gets its first line only."""
        failed = text.startswith(_ERROR_TAG)
        message = text.removeprefix(_ERROR_TAG).strip()
        if failed:
            logger.warning("Bot %s chart: %s", bot_id, message)
            first_line = (message.splitlines() or [_UNSAID_FAILURE])[0]
            self._show_status(first_line[:_MAX_STATUS_CHARS], True)
        else:
            logger.info("Bot %s chart: %s", bot_id, message)

    def draw(self, overlay: BotOverlay | None) -> None:
        if self._chart is not None:
            self._chart.show_overlay(overlay or BotOverlay())

    def fit_levels(self) -> bool:
        return self._chart.fit_levels() if self._chart is not None else False

    def close(self) -> None:
        """Releases the chart's stream and its load in flight. Safe to call twice."""
        self._live_stream.follow_chart(None)
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
