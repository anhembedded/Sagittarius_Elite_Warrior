# Epic: Báo cáo & Phân tích Chỉ số Tài chính Nâng cao (Advanced Financial Analytics & Reports Epic)

**Mã Epic:** `BOT-106`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🟡 **3/3 task con xong phần domain (22/09) — trình bày (UI) chưa làm cho `BOT-106B`/`BOT-106C`: QML đích (`BackTestTradeLogs.qml`, `MonthlyReturnsHeatmap.qml`, `DrawdownUnderwaterCard.qml`) đã bị gỡ khỏi codebase trước `EPIC-025`; cần một task PySide6 riêng (`ui-presentation-rule.md`) khi màn Backtest cần hiển thị các chỉ số này**  
**Ưu tiên:** 📈 **P2 — Phân tích Hiệu suất & Đo lường Rủi ro (Performance & Risk Analytics)**  
**Liên quan:** [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md), [`BOT-057`](../completed/BOT-057_backtest_trade_logs_table.md), [`BOT-056`](../completed/BOT-056_backtest_chart_canvas.md)

---

## 1. Mục tiêu Epic

Nâng cấp bảng báo cáo hiệu suất Backtest từ mức 4 chỉ số cơ bản (Net PnL, Win Rate, Max DD %, Profit Factor) lên **Bộ công cụ Định lượng Chuyên nghiệp**:
1. **Chỉ số Chất lượng Vốn & Lợi suất điều chỉnh rủi ro**: Sharpe Ratio, Sortino Ratio, Calmar Ratio, Thời gian chịu lỗ lớn nhất (Max Drawdown Duration), Chuỗi thắng/thua liên tiếp dài nhất.
2. **Phân tích Hiệu quả Vào/Thoát Lệnh (MAE/MFE Analysis)**: Đo lường mức chịu lỗ tối đa (Maximum Adverse Excursion) và mức lợi nhuận tiềm năng tối đa (Maximum Favorable Excursion) của từng lệnh giao dịch.
3. **Trực quan hóa Dữ liệu Chuyên sâu (Visual Reports)**:
   - Biểu đồ sụt giảm vốn (Drawdown / Underwater Chart).
   - Bảng nhiệt lợi suất theo tháng & năm (Monthly/Annual Returns Heatmap).

---

## 2. Danh sách Task thành phần

| Task ID | Tên Nhiệm vụ | Độ phức tạp | Mô tả tóm tắt |
| :--- | :--- | :---: | :--- |
| ✅ **[`BOT-106A`](../completed/BOT-106A_advanced_metrics_sharpe_sortino_drawdown_duration.md)** | **Sharpe, Sortino, Calmar & Max Drawdown Duration** | 🟡 `M` | **Xong (20/08).** Mở rộng `BacktestMetrics` tính toán các chỉ số định lượng theo chuẩn tài chính quốc tế. |
| ✅ **[`BOT-106B`](../completed/BOT-106B_mae_mfe_trade_excursion_analysis.md)** | **MAE / MFE Trade Excursion Analysis** | 🟡 `M` | **Xong phần domain (22/09).** MAE/MFE tính đúng ở Static Backtest; vô hiệu ở Historical Tick Backtest cho tới khi [`BUG-133`](../bug_report/incomplete/BUG-133_tick_backtest_never_checks_intrabar_stops.md) đóng. Trình bày (Trade Logs) chưa làm — QML đích không còn tồn tại. |
| ✅ **[`BOT-106C`](../completed/BOT-106C_drawdown_chart_and_monthly_heatmap.md)** | **Drawdown Underwater Chart & Monthly Heatmap View** | 🟡 `M` | **Xong phần domain (22/09).** `calculate_drawdown_series`/`calculate_monthly_returns`/`calculate_yearly_returns`, đối chiếu chéo với `BacktestMetrics`. Trình bày (2 QML component gốc) chưa làm — QML đích không còn tồn tại. |
