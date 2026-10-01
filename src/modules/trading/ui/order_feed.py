"""
@brief `OrderFeed` — sự thật của một lệnh/vị thế đến từ sàn, một nơi xử lý,
nhiều nơi hiển thị (`EPIC-021H`).

@details Câu hỏi phân xử của `architecture-rule.md` §6.2 — "màn khác muốn
biết chuyện này có vô lý không?" — trả lời không vô lý: bảng lệnh, chart
marker (`BOT-009`'s Trade Markers Manager, đang chờ đúng `OrderFilledEvent`
này), và log đều quan tâm khi một lệnh khớp hoặc một vị thế đổi. Feed thứ
tư cạnh `SyncProgressFeed`/`HealthFeed` — không tạo hình dạng thứ năm.

`SystemErrorFeed` từng được kể ở đây là Feed thứ ba; `BUG-126` đã xoá nó, vì
**không ai dựng nó cả** nên hai event lỗi nó đăng ký chảy vào hư không. Dòng
docstring đó chính là một trong hai "tham chiếu" khiến HLD §3.5 xếp nó vào
diện *live, do not delete* — grep văn bản không phân biệt được một lần **nhắc
tên** với một lần **import**. Nay việc đó do `shell/system_failure_log.py`
làm, và `tests/unit/architecture/test_a_bus_subscriber_is_constructed.py` đọc
**AST** nên một docstring không thể làm nó im lặng nữa.

`EPIC-028C` — một Feed nghe **một** venue: Futures và Spot chạy cùng lúc trên
cùng một bus, nên mỗi màn dựng Feed với venue của chính nó và event của venue
kia không bao giờ tới bảng của màn này (một lệnh Spot khớp không hiện trong
bảng Futures).

`EPIC-028J` — tóm tắt tài khoản (`AccountSummaryChangedEvent`/
`AccountSummaryStaleEvent`) đi qua cùng Feed này: cùng một sự thật tài khoản
của một venue, cùng bộ lọc venue, nên bàn giao dịch không dựng Feed thứ hai.

Phát lại nguyên vẹn `OrderFilledEvent`/`PositionChangedEvent`/
`PositionClosedEvent` (không chuẩn hoá thành DTO riêng): cả ba đã là kiểu
miền ổn định, có tên rõ ràng (`EPIC-021E`/`BUG-086`) — khác
`HealthUpdatedEvent`'s payload thô cần chuẩn hoá, ở đây không có gì để
chuẩn hoá thêm mà không mất thông tin.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_changed_event import (
    AccountSummaryChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_stale_event import (
    AccountSummaryStaleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.holdings_changed_event import (
    HoldingsChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.live_order_blocked_event import (
    LiveOrderBlockedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.base_feed import BaseFeed
from sagittarius_engine.interfaces.i_event_bus import IEventBus


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
    #: Mang một `HoldingsChangedEvent` (`EPIC-027O`).
    holdingsChanged = Signal(object)
    #: Mang một `AccountSummaryChangedEvent` (`EPIC-028J`).
    accountSummaryChanged = Signal(object)
    #: Mang một `AccountSummaryStaleEvent` (`EPIC-028J`).
    accountSummaryStale = Signal(object)

    def __init__(
        self,
        event_bus: IEventBus,
        venue: TradingVenue,
        parent: QObject | None = None,
    ) -> None:
        # Set before `super().__init__`: `BaseFeed.__init__` subscribes.
        self._venue = venue
        super().__init__(event_bus, parent)

    def _subscribe(self) -> None:
        self._events.on(OrderFilledEvent, self._on_order_filled)
        self._events.on(PositionChangedEvent, self._on_position_changed)
        self._events.on(PositionClosedEvent, self._on_position_closed)
        self._events.on(LiveOrderBlockedEvent, self._on_order_blocked)
        self._events.on(HoldingsChangedEvent, self._on_holdings_changed)
        self._events.on(AccountSummaryChangedEvent, self._on_summary_changed)
        self._events.on(AccountSummaryStaleEvent, self._on_summary_stale)

    def _on_order_filled(self, event: Any) -> None:
        if event.venue is self._venue:
            self.orderFilled.emit(event)

    def _on_position_changed(self, event: Any) -> None:
        if event.venue is self._venue:
            self.positionChanged.emit(event)

    def _on_position_closed(self, event: Any) -> None:
        if event.venue is self._venue:
            self.positionClosed.emit(event)

    def _on_order_blocked(self, event: Any) -> None:
        if event.venue is self._venue:
            self.orderBlocked.emit(event)

    def _on_holdings_changed(self, event: Any) -> None:
        if event.venue is self._venue:
            self.holdingsChanged.emit(event)

    def _on_summary_changed(self, event: Any) -> None:
        if event.venue is self._venue:
            self.accountSummaryChanged.emit(event)

    def _on_summary_stale(self, event: Any) -> None:
        if event.venue is self._venue:
            self.accountSummaryStale.emit(event)
