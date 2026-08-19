# Nhiệm vụ: Sharpe, Sortino, Calmar & Max Drawdown Duration Metrics

**Mã Task:** `BOT-106A`  
**Thuộc Epic:** [`BOT-106`](BOT-106_advanced_financial_analytics_and_reports_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog**  
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

- Invariant tests: Xử lý an toàn khi $\sigma = 0$ (không chia cho 0, không sinh `NaN`/`Inf`).
- Hiển thị đầy đủ trên Popup mở rộng của Performance Metrics Panel (`BackTestPerformanceMetrics.qml`).
