"""
@brief `BaseFeed` — hợp đồng cho "một sự thật hệ thống, một nơi xử lý, nhiều
nơi hiển thị".

@details
Đây là **điểm hạ cánh có tên** cho quy tắc thăng cấp ở
`.agents/rules/architecture-rule.md` §6.3, tồn tại theo §7 của cùng file: một
điểm mở rộng đã chốt thì phải có type trong code, không được chỉ nằm trong tài
liệu — vì tài liệu là thứ phải đi tìm mới thấy, còn type thì đập vào mắt khi
đọc code.

@par Khi nào viết một Feed mới — công thức thăng cấp
Một sự thật đang là **riêng của một màn** (Qt signal nội bộ trong presenter)
trở thành **sự thật hệ thống** ngay khi màn thứ hai cần biết nó. Lúc đó:

1. Cho nơi sinh ra sự thật đó **phát một event lên `IEventBus`** thay vì (hoặc
   cùng với) emit Qt signal nội bộ.
2. Viết một lớp con `BaseFeed`, cài `_subscribe()` để nghe event đó và chuẩn
   hoá payload thành **một** dataclass của tầng presentation.
3. Màn nào cần thì `connect` vào signal của Feed. **Không** màn nào tự
   `event_bus.on(...)` cùng event đó nữa.

Bước 3 là điểm mấu chốt của cả `EPIC-008`: nhiều màn cùng `event_bus.on()` một
event nghĩa là logic xử lý bị nhân bản đúng bằng số màn —
`HealthUpdatedEvent` từng có **3** bản định dạng cùng một `dict`, và
`SingleSyncProgressEvent` có **2** handler độc lập. Feed tồn tại để chuẩn hoá
đúng **một lần**.

@par Khi nào KHÔNG viết Feed
Sự thật chỉ một màn quan tâm (`history của tôi load xong`, `stream của tôi
start được`) thì **giữ Qt signal nội bộ**. Đẩy nó lên bus là rò rỉ: mọi màn đều
có thể nghe, và nhìn code không còn biết ai phụ thuộc ai. Thăng cấp **khi
consumer thứ hai xuất hiện thật**, không thăng trước (§6.3).
"""

from __future__ import annotations

from abc import abstractmethod

from PySide6.QtCore import QObject
from sagittarius_engine.extensions.pyside_mvc.mvc.qt_event_bridge import QtEventBridge
from sagittarius_engine.interfaces.i_event_bus import IEventBus


class BaseFeed(QObject):
    """
    @brief Lớp cha của mọi Feed: đăng ký một lần lên bus, chuẩn hoá, phát lại
    cho nhiều nơi hiển thị.

    @details Không dùng `abc.ABCMeta` ở đây: `QObject` có metaclass riêng của
    Shiboken, trộn hai metaclass là `TypeError` lúc định nghĩa lớp. Ràng buộc
    được giữ bằng `@abstractmethod` + `raise NotImplementedError` trong thân
    hàm — lớp con quên cài thì vỡ ngay lần dựng đầu tiên, kèm tên phương thức.

    Lớp con **chỉ** cần cài `_subscribe()`. Việc dựng `QtEventBridge`, gỡ đăng
    ký khi tắt, và tính idempotent của `stop()` đã nằm sẵn ở đây để không lớp
    con nào quên.
    """

    def __init__(self, event_bus: IEventBus, parent: QObject | None = None) -> None:
        """
        @param event_bus Luôn được bọc bằng `QtEventBridge` (`EPIC-008D`),
        không bao giờ dùng trực tiếp: event có thể được phát từ thread nền
        (`runtime.tasks.failed` là một ví dụ thật), và chạm Qt object ngoài
        main thread đúng là lớp lỗi `BUG-031`. Bọc ở lớp cha để một Feed mới
        **không thể** quên bước này.
        """
        super().__init__(parent)
        self._events = QtEventBridge(event_bus, parent=self)
        self._subscribe()

    @abstractmethod
    def _subscribe(self) -> None:
        """
        @brief Đăng ký các event lớp con quan tâm, qua `self._events.on(...)`.

        @details Gọi tự động trong `__init__`. Dùng `self._events` chứ **không**
        dùng thẳng `event_bus`, nếu không sẽ mất bước hop về main thread và mất
        luôn khả năng gỡ đăng ký ở `stop()`.
        """
        raise NotImplementedError(
            f"{type(self).__name__} phải cài _subscribe() — xem BaseFeed's docstring"
        )

    def stop(self) -> None:
        """@brief Gỡ mọi đăng ký Feed này đã tạo. Idempotent."""
        self._events.off_all()
