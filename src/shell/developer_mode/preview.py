"""`EPIC-033P` — the Developer mode with a few seconds of a running app's bus.

Offline: no container, no engine, no network. The log is filled directly with
the records a recorder would have drained, one of them a handler that raised.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.shell.developer_mode.bus_event_recorder import (
    BusEventRecord,
)
from Sagittarius_Elite_Warrior.src.shell.developer_mode.developer_view import (
    DeveloperView,
)

PREVIEW_KEY = "developer_mode"
_START = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
_EVENTS = (
    ("MarketTickEvent", 3, None),
    ("CandleClosedEvent", 2, None),
    ("SignalGeneratedEvent", 1, None),
    ("SignalGeneratedEvent", None, "on_signal: ValueError: no armed strategy"),
    ("HealthUpdatedEvent", 0, None),
)


def build_preview() -> QWidget:
    view = DeveloperView()
    view.append_events(
        [
            BusEventRecord(
                _START + timedelta(milliseconds=150 * i), event, handlers, failure
            )
            for i, (event, handlers, failure) in enumerate(_EVENTS)
        ]
    )
    view.show_lost(12)
    view.resize(1100, 600)
    return view
