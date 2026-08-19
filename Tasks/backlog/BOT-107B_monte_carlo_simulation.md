# Nhiệm vụ: Mô phỏng Monte Carlo & Đánh giá Nguy cơ Phá sản (Risk of Ruin)

**Mã Task:** `BOT-107B`  
**Thuộc Epic:** [`BOT-107`](BOT-107_strategy_robustness_and_monte_carlo_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-021`](../completed/BOT-021_static_backtest_engine.md), [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md)

---

## 1. Mục tiêu

Áp dụng phương pháp mô phỏng Monte Carlo để đánh giá độ ổn định của chiến lược trong tương lai:
1. **Trade Reshuffling (Xáo trộn Thứ tự Lệnh)**:
   - Lấy danh sách $N$ lệnh đã thực hiện trong quá khứ.
   - Chạy $M = 5,000$ đến $10,000$ lần xáo trộn ngẫu nhiên thứ tự các lệnh (sampling with/without replacement).
2. **Tính toán Phân phối Rủi ro**:
   - **Xác suất Phá sản (Risk of Ruin %)**: Tỷ lệ kịch bản mà tài khoản bị sụt giảm quá $50\%$ hoặc $100\%$.
   - **p95 / p99 Worst-Case Drawdown**: Mức sụt giảm vốn tồi tệ nhất ở mức tin cậy 95% và 99%.
   - **Median Expected Return**: Lợi nhuận kỳ vọng trung vị.
3. **Trực quan hóa**:
   - Vẽ chùm đường Equity mô phỏng (Monte Carlo Spaghetti Chart) và biểu đồ phân phối xác suất Max Drawdown.
