"""`EPIC-019B` — `HealthFeed` wiring, pulled out of `DashboardPresenter` and
`BackTestPresenter`: both screens independently constructed a `HealthFeed`,
connected `healthUpdated`, and carried near-identical
`_trigger_initial_health_check()`/`_on_health_report()` methods — the
wiring `HealthFeed` itself was built to make each screen never repeat
(see `health_feed.py`'s own docstring), still repeated once per screen.

Mirrors `symbol_options_coordinator.py`'s shape: a plain class (not
`QObject`), reporting through an injected `emit_log` callable rather than
holding a Presenter reference — the one difference between the two
screens' behavior (which log call they end with) stays at the call site,
not inside this class.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.presentation.ui.common.health_feed import HealthFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.health_status_report import (
    HealthStatusReport,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus


class HealthCheckCoordinator:
    """One `HealthFeed` per screen, asked for a fresh reading on open and
    reporting every update through `emit_log`."""

    def __init__(
        self,
        event_bus: IEventBus,
        emit_log: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        self._emit_log = emit_log
        self._health_feed = HealthFeed(event_bus, parent=parent)
        self._health_feed.healthUpdated.connect(self._on_report)

    def request_initial_check(self) -> None:
        """Xin số liệu sức khoẻ tươi ngay khi mở màn.

        Trước `EPIC-008G` hàm này resolve `HealthCheckQuery` rồi **tự dựng
        một `HealthUpdatedEvent`** để gọi thẳng handler của chính mình —
        cách vá cho việc `HealthExtension.boot()` chỉ phát đúng một lần lúc
        `app.boot()`, trước khi presenter (lazy) kịp tồn tại. `EPIC-008E`
        thay bằng cặp request/response thật, nên giờ chỉ cần hỏi.
        """
        self._health_feed.request_refresh()

    def _on_report(self, report: HealthStatusReport) -> None:
        """Đã ở main thread — `BaseFeed` bọc `QtEventBridge` sẵn."""
        self._emit_log(report.to_log_line())
