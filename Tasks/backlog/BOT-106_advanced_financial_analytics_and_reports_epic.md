# Epic: Báo cáo & Phân tích Chỉ số Tài chính Nâng cao (Advanced Financial Analytics & Reports Epic)

**Mã Epic:** `BOT-106`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** ✅ **4/4 task con xong (22/09)** — domain (`106A`/`106B`/`106C`) và trình bày PySide6 thật (`106D`: cột MAE/MFE trong Trade Logs, tab Drawdown, tab Returns) đều đã xong; MAE/MFE vẫn vô hiệu ở Historical Tick Backtest cho tới khi [`BUG-133`](../bug_report/incomplete/BUG-133_tick_backtest_never_checks_intrabar_stops.md) đóng  
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
| ✅ **[`BOT-106B`](../completed/BOT-106B_mae_mfe_trade_excursion_analysis.md)** | **MAE / MFE Trade Excursion Analysis** | 🟡 `M` | **Xong phần domain (22/09).** MAE/MFE tính đúng ở Static Backtest; vô hiệu ở Historical Tick Backtest cho tới khi [`BUG-133`](../bug_report/incomplete/BUG-133_tick_backtest_never_checks_intrabar_stops.md) đóng. Trình bày (Trade Logs) → [`BOT-106D`](../completed/BOT-106D_present_mae_mfe_drawdown_and_monthly_returns.md) ✅. |
| ✅ **[`BOT-106C`](../completed/BOT-106C_drawdown_chart_and_monthly_heatmap.md)** | **Drawdown Underwater Chart & Monthly Heatmap View** | 🟡 `M` | **Xong phần domain (22/09).** `calculate_drawdown_series`/`calculate_monthly_returns`/`calculate_yearly_returns`, đối chiếu chéo với `BacktestMetrics`. Trình bày → [`BOT-106D`](../completed/BOT-106D_present_mae_mfe_drawdown_and_monthly_returns.md) ✅. |
| ✅ **[`BOT-106D`](../completed/BOT-106D_present_mae_mfe_drawdown_and_monthly_returns.md)** | **Present MAE/MFE, Drawdown Chart & Monthly Returns (PySide6)** | 🟡 `M` | **Xong (22/09).** Cột MAE/MFE trong chi tiết dòng Trade Logs; 2 tab mới "DRAWDOWN"/"RETURNS" cạnh "TRADE LIST"/"BACKTEST LOG" — biểu đồ underwater (`pyqtgraph`, không dùng `ChartCard`) và bảng nhiệt tháng/năm (`QGridLayout`, tô màu qua `QPalette` chứ không `setStyleSheet()`, giữ ratchet styling không tăng). |
