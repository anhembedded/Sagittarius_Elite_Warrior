"""`EPIC-034G` — a mode's Live stream command, driving and following the
live chart in front (`live_stream_command.py` declares it).

Presenter-owned like `ChartCommandMirror` (`async-ui-action-rule.md` §2): a
mode builds a `LiveStreamMirror`, binds it, and follows the chart in front.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    chart_command_id,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_stream_command import (
    LIVE_STREAM,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_mirror import ActionMirror


class LiveStreamMirror(ActionMirror):
    """@brief A mode's Live stream command, driving and following the live
    chart in front."""

    def __init__(self, prefix: str, parent: QObject | None = None) -> None:
        super().__init__({LIVE_STREAM: chart_command_id(prefix, LIVE_STREAM)}, parent)

    def follow_chart(self, chart: LiveCandleChart | None) -> None:
        """Follows `chart`'s stream action; `None` means no chart, and the
        command is off."""
        self.follow(
            {LIVE_STREAM: chart.live_stream_action} if chart is not None else None
        )
