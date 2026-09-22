# Nhiệm vụ: Biểu đồ Sụt giảm Vốn (Drawdown Underwater) & Bảng nhiệt Lợi nhuận Hàng tháng (Monthly Heatmap)

**Mã Task:** `BOT-106C`  
**Thuộc Epic:** [`BOT-106`](BOT-106_advanced_financial_analytics_and_reports_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** ✅ Done (2026-09-22)  
**Dependencies:** [`BOT-056`](../completed/BOT-056_backtest_chart_canvas.md), [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md)

---

## 1. Mục tiêu

Xây dựng 2 component trực quan hóa dữ liệu hiệu suất chuyên sâu cho màn Backtest:
1. **Drawdown Underwater Chart (Biểu đồ Sụt giảm Vốn)**:
   - Thể hiện mức sụt giảm vốn từ đỉnh cũ (theo %) kéo dài theo trục thời gian dưới dạng diện tích màu đỏ (Underwater Area Chart).
   - Giúp người dùng nhìn rõ ngay các giai đoạn "khủng hoảng" của chiến lược.
2. **Monthly / Annual Returns Heatmap (Bảng nhiệt Lợi nhuận Tháng & Năm)**:
   - Lưới ma trận 12 cột (Tháng 1 $\rightarrow$ Tháng 12) $\times$ $N$ dòng (Năm 2022, 2023, 2024...).
   - Ô có màu xanh đậm (lãi cao), xanh nhạt (lãi vừa), đỏ nhạt (lỗ nhẹ), đỏ đậm (lỗ nặng). Cột cuối cùng tổng kết `YTD Return (%)`.

---

## 2. Triển khai

1. **Domain / Application**:
   - `monthly_returns_calculator.py`: Nhóm `equity_curve` theo tháng/năm, tính toán ROI từng tháng.
   - `drawdown_series_calculator.py`: Tính toán chuỗi % sụt giảm `drawdown_curve: list[tuple[float, float]]`.
2. **Presentation**:
   - Component QML `MonthlyReturnsHeatmap.qml` & Subplot `DrawdownUnderwaterCard.qml`.

## Implementation notes (2026-09-22)

- **Domain, done**: `calculate_drawdown_series(equity_curve)` (`contracts/drawdown_series_calculator.py`) — cùng định nghĩa running-peak với `BacktestMetrics._max_drawdown_percent`, nhưng trả về **toàn bộ chuỗi** một điểm mỗi điểm `equity_curve`, không rút gọn về một số. `calculate_monthly_returns`/`calculate_yearly_returns` (`contracts/monthly_returns_calculator.py`) — nhóm theo (năm, tháng) lịch của chính mốc thời gian mỗi điểm `equity_curve` (đã UTC — bất biến `BOT-097`), lợi nhuận một tháng đo từ equity mang sang từ tháng trước (hoặc `initial_balance` cho tháng đầu) tới điểm cuối cùng trong tháng đó — không đo từ điểm đầu tháng, tránh làm mất giá trị vị thế đã có sẵn khi bước vào tháng. `calculate_yearly_returns` nén các tháng đã biết của một năm bằng tích lũy (`math.prod`), đúng cho một năm còn đang chạy dở vì chỉ nhân đúng những tháng đã thực sự xảy ra.
- **2 module test mới**, 14 test, gồm 1 test đối chiếu chéo bắt buộc: `max(v for _, v in calculate_drawdown_series(curve))` phải khớp `BacktestMetrics.compute(...).max_drawdown_percent` trên cùng một đường cong — khoá chặt "cùng định nghĩa, không phải định nghĩa thứ hai" mà docstring của module tuyên bố. Toàn bộ xanh; `ruff`/`mypy` sạch.
- **Presentation: ngoài phạm vi, không phải bỏ sót.** `MonthlyReturnsHeatmap.qml`/`DrawdownUnderwaterCard.qml` không dựng được — QML đã bị gỡ khỏi codebase này trước `EPIC-025`. Domain-only là điểm dừng đúng, cùng khuôn với `BOT-106B`; UI thật (PySide6, theo `ui-presentation-rule.md`) được ghi thành task riêng có theo dõi —
  [`BOT-106D`](BOT-106D_present_mae_mfe_drawdown_and_monthly_returns.md) ✅ — thay vì chỉ ghi bằng văn xuôi (self-review PR #255, 22/09; `BOT-106D` xong cùng ngày).
