"""`EPIC-028M` — a desk's equity chart: its own venue's equity curve, the
backlog first, then every sample as it arrives (`EPIC-021M`).

@details The single Trading screen drew this chart from its presenter; it
moved here when that screen left, so a desk keeps it and the desk's presenter
stays a composition. The ADR lists the equity chart among the parts both
desks share (`DECISION_2026-09-29_two_trading_desks.md`).

**Subscribe, then read (`BUG-100`).** The recorder outlives every screen, so a
desk opened mid-session draws the whole backlog at once. The feed is
connected before the backlog is read: a sample recorded between the two is
then drawn twice at the same timestamp, which `ChartCard.append_closed_candle`
replaces in place, rather than lost.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_chart_adapter import (
    equity_sample_to_candle,
    equity_samples_to_candles,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_feed import EquityFeed
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard


class DeskEquity(QObject):
    """@brief Keeps one desk's equity chart drawn."""

    def __init__(
        self,
        chart: ChartCard,
        curve: IEquityCurve,
        feed: EquityFeed,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._chart = chart
        feed.equitySampled.connect(self._on_sampled)
        chart.render_historical_data(equity_samples_to_candles(curve.samples()))

    def _on_sampled(self, event: EquitySampledEvent) -> None:
        self._chart.append_closed_candle(*equity_sample_to_candle(event.sample))
