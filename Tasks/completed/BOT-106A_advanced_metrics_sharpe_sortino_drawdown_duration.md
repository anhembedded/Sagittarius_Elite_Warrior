# Nhiệm vụ: Sharpe, Sortino, Calmar & Max Drawdown Duration Metrics

**Mã Task:** `BOT-106A`  
**Thuộc Epic:** [`BOT-106`](BOT-106_advanced_financial_analytics_and_reports_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** ✅ **Hoàn thành (2026-08-20)**  
**Dependencies:** [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md)

---

## 1. Mục tiêu

Mở rộng `src/domain/backtesting/backtest_metrics.py` để tính toán chính xác các chỉ số lượng hóa rủi ro:
1. **Sharpe Ratio (Annualized)**:
   $$\text{Sharpe} = \frac{\bar{R} - R_f}{\sigma_R} \times \sqrt{N_{periods}}$$
   (Đo lường lợi nhuận trên tổng độ biến động).
2. **Sortino Ratio (Annualized)**:
   $$\text{Sortino} = \frac{\bar{R} - R_f}{\sigma_{downside}} \times \sqrt{N_{periods}}$$
   (Chỉ tính toán rủi ro trên các phiên biến động giảm / thua lỗ).
3. **Calmar Ratio**:
   $$\text{Calmar} = \frac{\text{Lợi nhuận hàng năm (CAGR)}}{\text{Max Drawdown (\%)}}$$
4. **Max Drawdown Duration (Thời gian sụt giảm vốn dài nhất)**:
   - Tính số ngày / số thanh nến dài nhất mà đường Equity nằm dưới đỉnh cao nhất (Peak-to-Recovery Duration).
5. **Max Consecutive Wins / Losses (Chuỗi lệnh thắng/thua liên tiếp dài nhất)**.

---

## 2. Tiêu chí Nghiệm thu

- [x] Invariant tests: Xử lý an toàn khi $\sigma = 0$ (không chia cho 0, không sinh `NaN`/`Inf`).
- [x] Hiển thị đầy đủ trên Popup mở rộng của Performance Metrics Panel (`ExtendedMetricsModal.qml`).

---

## 3. Ghi chú Triển khai

- `BacktestMetrics` thêm 6 field mới: `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`, `max_drawdown_duration_bars`, `max_consecutive_wins`, `max_consecutive_losses` — tất cả có default để không phá các call site `BacktestMetrics(...)` dựng trực tiếp (không qua `compute()`) đang có sẵn trong test suite.
- $N_{periods}$ (hệ số annualize) tự suy ra từ khoảng cách trung bình giữa các điểm `equity_curve` (365.25 ngày ÷ số giây/bar trung bình) — **không** cần thêm tham số `timeframe` mới vào `compute()`, vì mọi timestamp cần thiết đã có sẵn trong chính `equity_curve`.
- Risk-free rate mặc định = 0 (repo không có input risk-free rate ở đâu để trừ) — khớp default của TradingView.
- **Bug thật phát hiện khi verify bằng cách chạy code thật** (không đoán tay): chuỗi return per-bar hằng số về mặt toán học (vd tăng đều 1%/bar) vẫn cho `statistics.stdev()` ra một số cỡ `1e-16` chứ không đúng `0.0` do sai số dấu phẩy động — chia cho số đó ra Sharpe ~3.2 triệu tỷ thay vì `0.0` như kỳ vọng. Sửa bằng `math.isclose(..., abs_tol=1e-9)` thay vì so sánh `== 0` trực tiếp.
- Max Drawdown Duration tính theo **số bar** (không phải ngày thực), giữ đúng tinh thần "timeframe-independent" mà `avg_bars_per_trade` (BOT-079) đã lập tiền lệ và tự ghi chú lý do ngay tại chỗ.
- Max Consecutive Wins/Losses: lệnh hoà vốn (`pnl == 0`) reset cả 2 chuỗi, không tính vào chuỗi nào — cùng cách TradingView xử lý "scratch trade".
- Sharpe/Sortino/Calmar/Max Drawdown Duration được tính từ `equity_curve`, **độc lập với `trades`** — một lần chạy 0 lệnh nhưng có drawdown/hồi phục thật trên đường vốn vẫn ra số thật, không phải `0.0` giả (giữ đúng tinh thần `max_drawdown_percent` đã có từ trước task này).
- Nối vào `ExtendedMetricsModal.qml`/`build_extended_stat_cards()` — không cần sửa QML vì `Repeater` đã đọc động theo model, tự thêm card mới không cần đổi layout.
- 20 test mới (`test_backtest_metrics.py` + `test_performance_metrics_view.py`), bao gồm test tái hiện đúng bug số học nêu trên trước khi thêm guard. Toàn bộ 1534 test `tests/unit/` + 41 sanity pass, `ruff` sạch.
