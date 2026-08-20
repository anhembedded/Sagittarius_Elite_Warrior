from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)

#: BOT-081 — every entry here is true for every run TODAY because the
#: underlying feature simply doesn't exist yet in the engine — there is no
#: live config to branch on. This is the single place that changes when one
#: of those features ships (task's own §5: "mỗi task đó xoá bớt một dòng
#: khỏi danh sách"), rather than a doc/comment scattered across files that
#: nobody remembers to update. Genuinely per-run items (out-of-sample
#: presence, execution mode once BOT-073 ships) are computed in
#: `build_backtest_limitations()` below, not listed here.
#: BOT-105 — the sizing/pyramiding/Short/leverage line that used to sit
#: here was removed: Short (BOT-050), pyramiding + flexible sizing
#: (BOT-104) and leverage (BOT-105) all shipped, so nothing in that claim
#: was still true.
_ALWAYS_APPLICABLE_LIMITATIONS = [
    "Chế độ đang chạy: Static — dựa trên nến đã đóng, không phải tick thật.",
    "Không mô phỏng slippage — mọi lệnh khớp đúng giá yêu cầu.",
    "Không mô phỏng độ trễ mạng / thời gian xử lý lệnh.",
    (
        "Không mô phỏng độ sâu sổ lệnh (orderbook depth) — lệnh luôn khớp "
        "trọn vẹn bất kể khối lượng."
    ),
    "Chưa có Stop Loss / Take Profit.",  # BOT-041
    (
        "Lệnh khớp tại giá mở nến kế tiếp — chặn lookahead bias, nhưng tạo "
        "độ trễ nhân tạo 1 nến."
    ),
    (
        'Phí giao dịch có thể chiếm phần lớn kết quả — xem "Total Fees Paid" '
        "ở chỉ số mở rộng."
    ),
]

_NO_OUT_OF_SAMPLE_NOTE = (
    "Không có kiểm định ngoài mẫu (out-of-sample) cho lần chạy này — khoảng "
    "dữ liệu quá ngắn để chia 70/30."
)


def build_backtest_limitations(result: BacktestResult) -> list[str]:
    """
    @brief BOT-081: every limitation that applies to THIS specific run —
    read from real per-run state where such state exists, not a static list
    copy-pasted once and left to rot.
    @details `result.out_of_sample` is the one item here with genuine
    per-run state (BOT-080): most ranges get a real in-sample/out-of-sample
    split, but a short enough range still comes back with `out_of_sample is
    None` — that's still worth disclosing for THAT run, even though
    out-of-sample validation exists in the app overall.
    """
    notes = list(_ALWAYS_APPLICABLE_LIMITATIONS)
    if result.out_of_sample is None:
        notes.append(_NO_OUT_OF_SAMPLE_NOTE)
    return notes
