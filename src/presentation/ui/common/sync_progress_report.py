"""
@brief `SyncProgressReport` — tiến độ đồng bộ một cặp symbol/interval, đã
chuẩn hoá cho hiển thị.

@details Trước `EPIC-008G`, hai màn cùng nghe `SingleSyncProgressEvent` và mỗi
màn tự đọc payload thô. Chỉ Data Management ghép chuỗi hiển thị; Backtest thì
không, nên khi cần một dòng tiến độ ở màn đó, người viết sẽ ghép **bản thứ
hai** — đúng cách `HealthUpdatedEvent` đã có tới ba bản định dạng. Kiểu này tồn
tại để câu chữ chỉ có một nơi sinh ra.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyncProgressReport:
    """
    @brief Một lần báo tiến độ đồng bộ.

    @details `frozen` — fan-out tới nhiều màn, màn này không được sửa thứ màn
    sau nhìn thấy. Payload tầng presentation, không lên bus, nên không bị ràng
    buộc kế thừa `BaseEvent` và giữ được bất biến.
    """

    symbol: str
    interval: str
    current: int
    total: int
    #: BOT-122: copied from `SingleSyncProgressEvent.correlation_id` —
    #: which screen's request this progress belongs to. Consumers filter on
    #: this, not on `symbol`/`interval` (two different actions can target
    #: the same one).
    correlation_id: str = ""

    @property
    def is_complete(self) -> bool:
        """@brief Đã kéo đủ chưa. `total <= 0` coi như chưa biết → chưa xong."""
        return self.total > 0 and self.current >= self.total

    def to_message(self) -> str:
        """@brief Dòng hiển thị dùng chung cho mọi màn."""
        return (
            f"Đang đồng bộ {self.symbol} {self.interval} "
            f"({self.current:,}/{self.total:,} nến)"
        )
