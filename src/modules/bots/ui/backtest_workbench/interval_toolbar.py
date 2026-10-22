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
#: The intervals a replay cannot judge truthfully yet (`BOT-232`, review round 1). Their candles do not
#: open on the epoch-aligned grid the replay counts and windows by: Binance's 3d candles open one day off
#: the epoch's multiples of three (measured on `data.binance.vision`, 2024-08: Aug 1, 4, 7), weekly ones on
#: Mondays (the epoch was a Thursday) and monthly ones on the 1st, whose length is 28 to 31 days where
#: `TimeFrame.to_seconds` says 30. Offered, a stored period would read "partly stored" with a Sync that
#: cannot clear it, and a month's 1-second prices would be replayed in the wrong month. Retire when:
#: the replay takes each bar's end from the venue's calendar and counts expected candles on its boundaries.
UNREPLAYED_INTERVALS = frozenset(
    {TimeFrame.THREE_DAYS, TimeFrame.ONE_WEEK, TimeFrame.ONE_MONTH}
)
#: What the picker offers: every interval the replay judges truthfully.
OFFERED_INTERVALS = tuple(
    interval for interval in TimeFrame if interval not in UNREPLAYED_INTERVALS
)
#: Said when the interval Run replays is unticked in the picker (`EPIC-040` F4).
_CURRENT_INTERVAL_TEXT = (
    "The interval Run replays stays pinned, so the row always shows it."
)


def interval_toolbar() -> ChartToolbar:
    """The interval, chosen the way every chart's timeframe is: the pinned intervals as actions and
    "More timeframes…", whose picker offers every interval the bot's market loads and the replay judges (`BOT-232`)."""
    toolbar = ChartToolbar(
        timeframes=[interval.value for interval in PINNED_INTERVALS],
        active=DEFAULT_INTERVAL.value,
        offered_codes=[interval.value for interval in OFFERED_INTERVALS],
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
