"""`EPIC-040D` — the Backtest workbench's interval: chosen the way every chart's timeframe is."""

from __future__ import annotations

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.chart_toolbar import (
    ChartToolbar,
)
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    CurrentStaysPinned,
)

#: The intervals pinned on the row at first; the picker offers every interval the bot's market
#: loads, and the result chart draws in the one that was run.
PINNED_INTERVALS = (
    TimeFrame.ONE_MINUTE,
    TimeFrame.FIVE_MINUTES,
    TimeFrame.FIFTEEN_MINUTES,
    TimeFrame.ONE_HOUR,
)
DEFAULT_INTERVAL = TimeFrame.FIFTEEN_MINUTES
#: Said when the interval Run replays is unticked in the picker (`EPIC-040` F4).
_CURRENT_INTERVAL_TEXT = (
    "The interval Run replays stays pinned, so the row always shows it."
)


def interval_toolbar() -> ChartToolbar:
    """The interval, chosen the way every chart's timeframe is: the pinned intervals as actions and
    "More timeframes…", whose picker offers every interval the bot's market loads (`BOT-232`)."""
    toolbar = ChartToolbar(
        timeframes=[interval.value for interval in PINNED_INTERVALS],
        active=DEFAULT_INTERVAL.value,
        keep_current_pinned=CurrentStaysPinned(_CURRENT_INTERVAL_TEXT),
    )
    toolbar.setObjectName("tbBacktestInterval")
    toolbar.setWindowTitle("Interval")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    _reach_by_tab(toolbar)
    return toolbar


def _reach_by_tab(toolbar: ChartToolbar) -> None:
    """A toolbar's buttons take no focus, and the drop-down this replaced did: the interval is a run
    parameter, so a person on the keyboard must still reach it (`ui-presentation-rule.md` §2). The
    buttons are rebuilt when the pins change, so the policy is set again after each rebuild."""

    def apply() -> None:
        actions = [
            *toolbar.timeframes.timeframe_actions(),
            toolbar.timeframes.more_action,
        ]
        for action in actions:
            button = toolbar.widgetForAction(action)
            if button is not None:
                button.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    toolbar.timeframes.rebuilt.connect(apply)
    apply()
