"""
@brief Payload cho các signal của màn Data Management (`EPIC-008G` §3).

@details
`ui_status_table_signal` từng là `Signal(str, str, str, str, str, str)` — **sáu
chuỗi cùng kiểu, phân biệt nhau chỉ bằng vị trí**. Hoán nhầm hai cột là lỗi
*thầm lặng*: Qt vẫn giao, model vẫn nhận, bảng vẫn vẽ — chỉ là "ngày đầu" nằm ở
cột "ngày cuối". `mypy` không bắt được vì cả sáu đều là `str`, và test cũng
truyền theo đúng thứ tự sai đó nếu người viết test hiểu nhầm giống người viết
code.

Đây là chỗ `code-rule.md` yêu cầu dataclass thay cấu trúc thô. Sáu chuỗi vị trí
còn tệ hơn một `dict`: `dict` ít nhất còn có tên khoá.

@par Vì sao đổi signal mà không đổi `upsert_row()`
Nguy hiểm nằm ở **biên signal** — nơi giá trị đi qua một hàng đợi cross-thread
và không còn chỗ nào cạnh nhau để so sánh. `upsert_row()` được gọi trực tiếp ở
`preview.py` và trong test, nơi lời gọi nằm ngay cạnh định nghĩa và đọc được;
đổi luôn chữ ký của nó chỉ lan rộng thay đổi mà không mua thêm an toàn.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class StatusRowUpdate:
    """
    @brief Một dòng của bảng Storage Vault.

    @details `frozen` — nó đi qua biên thread tới model; nơi nhận không được
    sửa thứ nơi gửi vừa mô tả.
    """

    symbol: str
    first_record: str
    last_record: str
    total_candles: str
    status_text: str
    interval: str = TimeFrame.ONE_MINUTE.value


@dataclass(frozen=True)
class GapInspectorPayload:
    """
    @brief Kết quả soi lỗ hổng dữ liệu của một cặp symbol/interval.

    @details Signal cũ là `Signal(str, str, int, int, float, list, list)` — bảy
    tham số vị trí, trong đó **hai `int` liền nhau** (`total_gaps`,
    `total_missing_candles`) và **hai `list` liền nhau** (`gaps`, `segments`).
    Hoán nhầm một trong hai cặp đó không sai kiểu, nên `mypy` im lặng và Qt vẫn
    giao — chỉ có con số/bảng hiển thị sai.
    """

    symbol: str
    interval: str
    total_gaps: int
    total_missing_candles: int
    coverage_percentage: float
    gaps: list[dict]
    segments: list[dict]
