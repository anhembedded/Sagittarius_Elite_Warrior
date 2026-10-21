"""`EPIC-036D2` — the Alerts screen with a day of a running app's alerts.

Offline: no container, no engine, no outbox. The view is shown a report built by hand, with
every delivery state the table can say and one channel failing, so the notice bar and the
words that carry severity are in the frame.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.alert_history_report import (
    AlertHistoryRow,
    ChannelHealth,
    ChannelOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState as State,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.alerts_view import (
    AlertsView,
)

#: `scripts/preview_qml.py` keys a preview by its parent directory name, `history`, which
#: says nothing across modules.
PREVIEW_KEY = "alerts_history"
_NOW = datetime(2026, 10, 20, 14, 30, tzinfo=UTC)
_DISCORD = "discord"
_TELEGRAM = "telegram"


def _row(
    alert_id: int,
    minutes_ago: int,
    kind: AlertKind,
    severity: Severity,
    subject: str,
    title: str,
    outcomes: tuple[ChannelOutcome, ...],
    count: int = 1,
) -> AlertHistoryRow:
    return AlertHistoryRow(
        alert_id,
        _NOW - timedelta(minutes=minutes_ago),
        kind,
        severity,
        subject,
        title,
        count,
        outcomes,
    )


def _outcome(channel: str, state: State, attempts: int = 1) -> ChannelOutcome:
    return ChannelOutcome(channel, state, attempts)


_ROWS = (
    _row(
        7,
        2,
        AlertKind.BOT_HALTED,
        Severity.CRITICAL,
        "grid-eth",
        "Bot grid-eth halted: stop-loss hit",
        (_outcome(_DISCORD, State.SENT), _outcome(_TELEGRAM, State.RETRYING, 2)),
    ),
    _row(
        6,
        9,
        AlertKind.ORDER_FILLED,
        Severity.INFO,
        "grid-eth",
        "Filled 0.25 ETH at 2 481.10",
        (_outcome(_DISCORD, State.SENT), _outcome(_TELEGRAM, State.SENT)),
        count=3,
    ),
    _row(
        5,
        41,
        AlertKind.APP_FAILURE,
        Severity.WARNING,
        "Application",
        "A background job raised an error",
        (_outcome(_DISCORD, State.SENT), _outcome(_TELEGRAM, State.FAILED, 5)),
    ),
    _row(
        4,
        95,
        AlertKind.ORDER_FILLED,
        Severity.INFO,
        "sol-dca",
        "Filled 12 SOL at 168.40",
        (_outcome(_DISCORD, State.DROPPED, 0), _outcome(_TELEGRAM, State.EXPIRED, 3)),
    ),
    _row(
        3,
        180,
        AlertKind.PRICE_FEED_STALE,
        Severity.WARNING,
        "spot-mainnet",
        "Price feed is stale",
        (),
    ),
)
_CHANNELS = (
    ChannelHealth(_DISCORD, failing=False, waiting=0),
    ChannelHealth(_TELEGRAM, failing=True, waiting=1),
)


def build_preview() -> QWidget:
    view = AlertsView()
    view.show_alert_history(_ROWS, _CHANNELS)
    view.resize(1100, 600)
    return view
