"""
@brief `SyncProgressFeed` — một nơi nghe `SingleSyncProgressEvent`, nhiều màn
hiển thị.

@details
Backtest và Data Management đều `event_bus.on(SingleSyncProgressEvent, ...)`.
Hai handler làm hai việc khác nhau — Backtest tương quan `action_id` của riêng
nó, Data Management ghép chuỗi hiển thị — nhưng **cả hai đều phải tự đọc
payload thô**, và chỉ một trong hai có câu chữ. Màn nào cần dòng tiến độ tiếp
theo sẽ ghép bản thứ hai; đó đúng là cách `HealthUpdatedEvent` đi tới ba bản
định dạng.

Feed chuẩn hoá một lần thành `SyncProgressReport`. Phần **riêng của từng màn**
(tương quan `action_id`) ở lại presenter — nó là sự thật riêng của màn đó, đúng
ranh giới `architecture-rule.md` §6.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.application.events.sync_events import (
    SingleSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.base_feed import BaseFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.sync_progress_report import (
    SyncProgressReport,
)


class SyncProgressFeed(BaseFeed):
    """
    @brief Chuẩn hoá tiến độ đồng bộ một lần, phát lại cho mọi màn.
    """

    #: Mang một `SyncProgressReport`.
    progressUpdated = Signal(object)

    def _subscribe(self) -> None:
        self._events.on(SingleSyncProgressEvent, self._on_progress)

    def _on_progress(self, event: Any) -> None:
        self.progressUpdated.emit(
            SyncProgressReport(
                symbol=str(getattr(event, "symbol", "")),
                interval=str(getattr(event, "interval", "")),
                current=int(getattr(event, "current", 0) or 0),
                total=int(getattr(event, "total", 0) or 0),
            )
        )
