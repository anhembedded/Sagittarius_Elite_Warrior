"""
@brief Payload cho các signal của màn Backtest (`EPIC-008G` §3).

@details `_backtestProgressSignal` từng là `Signal(int, str, int, int, float)`.
Hai `int` (`completed_bars`, `total_bars`) nằm **liền nhau**; hoán nhầm chúng
không sai kiểu nên `mypy` im lặng, Qt vẫn giao, và thanh tiến độ chỉ đơn giản
hiển thị sai — kiểu lỗi không có traceback để lần.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestProgress:
    """
    @brief Một lần báo tiến độ của một lần chạy backtest.

    @details `action_id` đi kèm payload chứ không tách ra làm tham số riêng:
    nó là **phần không thể thiếu** của "tiến độ này thuộc về lần chạy nào".
    Tách ra là mời gọi việc quên đối chiếu — đúng thứ hợp đồng
    action-ownership (`async-ui-action-rule.md`) tồn tại để chặn.
    """

    action_id: int
    phase: str
    completed_bars: int
    total_bars: int
    elapsed_seconds: float
