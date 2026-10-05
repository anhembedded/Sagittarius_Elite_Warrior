"""View → Load older candles and View → Load range… (`EPIC-033S`): two
commands that act on the Market chart in front.

Presenter-owned (`async-ui-action-rule.md` §2): built and held by
`MarketPresenter`, never registered. It owns no load bookkeeping either:
each `MarketChart` fences its own loads by generation and says when it is
loading; this object only routes the command to the chart in front and keeps
both commands off while no chart is open or the one in front loads.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

from .chart_history import HistoryRange
from .market_chart import MarketChart
from .market_commands import LOAD_OLDER, LOAD_RANGE
from .market_view import MarketView

logger = logging.getLogger("App.Trading.Market")

#: Load range… proposes this much before now when the chart in front has
#: nothing drawn yet.
_PROPOSED_SPAN = timedelta(days=7)


class ChartHistoryCommands(QObject):
    """@brief Load older candles and Load range…, for the chart in front."""

    #: Whether the two commands may run now.
    enabledChanged = Signal(bool)

    def __init__(
        self,
        view: MarketView,
        charts: Callable[[], Mapping[str, MarketChart]],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._charts = charts
        view.current_chart_changed.connect(lambda _symbol: self.refresh())

    def bind_commands(self, binder: ICommandBinder) -> None:
        ready = self._front_ready()
        binder.bind(
            LOAD_OLDER,
            self._on_load_older,
            enabled=self.enabledChanged,
            initially_enabled=ready,
        )
        binder.bind(
            LOAD_RANGE,
            self._on_load_range,
            enabled=self.enabledChanged,
            initially_enabled=ready,
        )

    def watch(self, chart: MarketChart) -> None:
        """Keeps the commands in step with `chart`'s loads."""
        chart.loadingChanged.connect(lambda _loading: self.refresh())

    def refresh(self) -> None:
        self.enabledChanged.emit(self._front_ready())

    def load_older(self) -> None:
        chart = self._front()
        if chart is not None:
            logger.info("[market] load older candles of %s", chart.shown_symbol)
            chart.load_older()

    def load_range(self) -> None:
        chart = self._front()
        if chart is None:
            return
        span = self._view.ask_history_range(chart.shown_symbol, self._proposal(chart))
        if span is None:
            return
        logger.info(
            "[market] load range of %s: %s to %s",
            chart.shown_symbol,
            span.start.isoformat(),
            span.end.isoformat(),
        )
        chart.load_range(span)

    def _on_load_older(self, _checked: bool) -> None:
        self.load_older()

    def _on_load_range(self, _checked: bool) -> None:
        self.load_range()

    def _front(self) -> MarketChart | None:
        return self._charts().get(self._view.current_symbol)

    def _front_ready(self) -> bool:
        chart = self._front()
        return chart is not None and not chart.loading

    @staticmethod
    def _proposal(chart: MarketChart) -> HistoryRange:
        """What the chart shows now, or the last week when it shows nothing."""
        drawn = chart.drawn_span()
        if drawn is not None:
            return drawn
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        return HistoryRange(now - _PROPOSED_SPAN, now)
