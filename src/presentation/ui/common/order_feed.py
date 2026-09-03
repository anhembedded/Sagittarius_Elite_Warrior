"""
@brief `OrderFeed` — sự thật của một lệnh/vị thế đến từ sàn, một nơi xử lý,
nhiều nơi hiển thị (`EPIC-021H`).

@details Câu hỏi phân xử của `architecture-rule.md` §6.2 — "màn khác muốn
biết chuyện này có vô lý không?" — trả lời không vô lý: bảng lệnh, chart
marker (`BOT-009`'s Trade Markers Manager, đang chờ đúng `OrderFilledEvent`
này), và log đều quan tâm khi một lệnh khớp hoặc một vị thế đổi. Feed thứ
tư cạnh `SyncProgressFeed`/`HealthFeed`/`SystemErrorFeed` — không tạo hình
dạng thứ năm.

Phát lại nguyên vẹn `OrderFilledEvent`/`PositionChangedEvent`/
`PositionClosedEvent` (không chuẩn hoá thành DTO riêng): cả ba đã là kiểu
miền ổn định, có tên rõ ràng (`EPIC-021E`/`BUG-086`) — khác
`HealthUpdatedEvent`'s payload thô cần chuẩn hoá, ở đây không có gì để
chuẩn hoá thêm mà không mất thông tin.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.domain.events.live_order_blocked_event import (
    LiveOrderBlockedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.base_feed import BaseFeed


class OrderFeed(BaseFeed):
    """@brief Chuẩn hoá sự thật lệnh/vị thế một lần, phát lại cho mọi màn."""

    #: Mang một `OrderFilledEvent`.
    orderFilled = Signal(object)
    #: Mang một `PositionChangedEvent`.
    positionChanged = Signal(object)
    #: Mang một `PositionClosedEvent` (`BUG-086`).
    positionClosed = Signal(object)
    #: Mang một `LiveOrderBlockedEvent` (`BUG-084`).
    orderBlocked = Signal(object)

    def _subscribe(self) -> None:
        self._events.on(OrderFilledEvent, self._on_order_filled)
        self._events.on(PositionChangedEvent, self._on_position_changed)
        self._events.on(PositionClosedEvent, self._on_position_closed)
        self._events.on(LiveOrderBlockedEvent, self._on_order_blocked)

    def _on_order_filled(self, event: Any) -> None:
        self.orderFilled.emit(event)

    def _on_position_changed(self, event: Any) -> None:
        self.positionChanged.emit(event)

    def _on_position_closed(self, event: Any) -> None:
        self.positionClosed.emit(event)

    def _on_order_blocked(self, event: Any) -> None:
        self.orderBlocked.emit(event)
