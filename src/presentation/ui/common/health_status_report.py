"""
@brief `HealthStatusReport` — trạng thái sức khoẻ hệ thống ở dạng đã sẵn sàng
hiển thị.

@details Trước `EPIC-008G`, hai màn tự đọc `dict` thô của `HealthUpdatedEvent`
và tự ghép chuỗi, ra **hai định dạng khác nhau** cho cùng một dữ liệu:

```
Backtest  : [Health] Trạng thái hệ thống: HEALTHY (Database: OK, EventBus: OK)
Dashboard : System Health: HEALTHY (DB: OK, Container: OK, EventBus: OK)
```

Khác nhau không chỉ ở chữ: Backtest **bỏ sót `Container`**. Đó là hệ quả điển
hình của việc mỗi màn tự chuẩn hoá — hai bản trôi khỏi nhau và không ai biết
bản nào đúng. `HealthFeed` chuẩn hoá đúng một lần thành kiểu này.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HealthStatusReport:
    """
    @brief Kết quả một lần đo sức khoẻ, đã chuẩn hoá.

    @details `frozen` — nó fan-out tới nhiều màn, màn này không được sửa thứ
    màn sau nhìn thấy. Giữ được bất biến vì đây là payload tầng presentation,
    không bao giờ lên bus nên không bị ràng buộc kế thừa `BaseEvent`.
    """

    #: `HEALTHY` / `DEGRADED` / … đã viết hoa.
    status: str

    #: Tên component → trạng thái, đã viết hoa. Giữ **nguyên vẹn** những gì
    #: engine trả về thay vì chọn sẵn vài khoá: chính việc Backtest tự chọn
    #: `database`+`event_bus` là lý do nó âm thầm mất `container`.
    components: dict[str, str] = field(default_factory=dict)

    def to_log_line(self) -> str:
        """
        @brief Một dòng log dùng chung cho mọi màn.

        @details Định dạng **đổi so với trước** ở cả hai màn — user đã duyệt
        (`EPIC-008G` §1). Đổi lấy việc hai màn không còn nói hai kiểu về cùng
        một sự thật.
        """
        # `capitalize()` khớp đúng cách `HealthExtension` tự log ở engine
        # (`health_module.py`), để dòng log của app và của engine đọc giống hệt
        # nhau thay vì lệch nhau một kiểu viết hoa.
        detail = ", ".join(
            f"{name.capitalize()}: {state}" for name, state in self.components.items()
        )
        return f"[Health] Trạng thái hệ thống: {self.status} ({detail})"
