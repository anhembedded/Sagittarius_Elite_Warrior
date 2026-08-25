"""
@brief `HealthFeed` — một nơi nghe `HealthUpdatedEvent`, nhiều màn hiển thị.

@details
Trước `EPIC-008G`, Backtest và Dashboard mỗi màn tự `event_bus.on(...)` cùng
sự kiện này rồi tự ghép chuỗi từ `dict` thô — **ba** bản định dạng cho một dữ
liệu, và hai bản trôi khỏi nhau đến mức Backtest **bỏ sót `Container`** mà
không ai phát hiện. Đúng thứ nguyên tắc nền của epic sinh ra để chặn.

@par Tại sao trước đây phải tự chế sự kiện
`HealthExtension.boot()` phát `HealthUpdatedEvent` **đúng một lần**, lúc
`app.boot()`. Presenter thì lazy — chỉ tồn tại khi user bấm vào màn đó lần
đầu, tức luôn **sau** thời điểm phát. Nên hai dòng `event_bus.on(...)` kia là
mã chết, và cả hai màn đã vá bằng cách resolve `HealthCheckQuery` rồi **tự dựng
một `HealthUpdatedEvent`** gọi thẳng handler của mình.

`EPIC-008E` đã thay bằng cặp request/response thật. `request_refresh()` dưới
đây phát `HealthCheckRequested`; `HealthExtension` đo lại và trả lời bằng
`HealthUpdatedEvent` đi qua đúng đường bus. Nhờ vậy màn hình **không cần biết**
`HealthCheckRequested` tồn tại — và số liệu là **tươi tại thời điểm mở màn**,
không phải ảnh chụp lúc boot.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.presentation.ui.common.base_feed import BaseFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.health_status_report import (
    HealthStatusReport,
)
from sagittarius_engine.extensions.health.health_check_requested import (
    HealthCheckRequested,
)
from sagittarius_engine.extensions.health.health_updated_event import HealthUpdatedEvent


class HealthFeed(BaseFeed):
    """
    @brief Chuẩn hoá sức khoẻ hệ thống một lần, phát lại cho mọi màn.
    """

    #: Mang một `HealthStatusReport`.
    healthUpdated = Signal(object)

    def _subscribe(self) -> None:
        self._events.on(HealthUpdatedEvent, self._on_health_updated)

    def request_refresh(self) -> None:
        """
        @brief Xin đo lại sức khoẻ ngay bây giờ; kết quả về qua `healthUpdated`.

        @details Màn hình gọi cái này khi mở, thay cho
        `_trigger_initial_health_check()` mà mỗi màn từng tự viết. Bất đồng bộ —
        **không** trả về gì; câu trả lời đi đường sự kiện như mọi cập nhật sức
        khoẻ khác, nên nơi hiển thị chỉ có duy nhất một đường vào.

        Không có `HealthExtension` nào đang chạy thì đây là no-op im lặng —
        hành vi đúng của một *yêu cầu*: hỏi thăm sức khoẻ không được phép làm
        chết màn hình vừa mở nó.
        """
        self._publish(HealthCheckRequested())

    def _on_health_updated(self, event: Any) -> None:
        status_dict = getattr(event, "status", {}) or {}
        components = status_dict.get("components", {}) or {}
        self.healthUpdated.emit(
            HealthStatusReport(
                status=str(status_dict.get("status", "unknown")).upper(),
                # Giữ nguyên mọi component engine trả về, không chọn lọc —
                # chính việc chọn lọc đã làm Backtest mất `container`.
                components={
                    str(name): str(state).upper() for name, state in components.items()
                },
            )
        )
