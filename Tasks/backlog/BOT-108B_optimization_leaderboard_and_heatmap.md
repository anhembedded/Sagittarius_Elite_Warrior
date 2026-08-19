# Nhiệm vụ: Optimization Leaderboard & 2D Parameter Heatmap UI

**Mã Task:** `BOT-108B`  
**Thuộc Epic:** [`BOT-108`](BOT-108_strategy_parameter_optimization_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-108A`](BOT-108A_parameter_grid_search_engine.md), [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md)

---

## 1. Mục tiêu

Xây dựng giao diện xem và nạp kết quả tối ưu hóa tham số:
1. **Optimization Leaderboard (Bảng Xếp hạng)**:
   - Hiển thị danh sách kết quả với các cột: `#`, `Tham số`, `Net PnL (%)`, `Sharpe Ratio`, `Max Drawdown (%)`, `Profit Factor`, `Total Trades`.
   - Cho phép sort theo bất kỳ cột nào.
   - Nút **"Áp dụng" (Apply)**: Click vào một dòng sẽ nạp ngay bộ tham số đó vào `BotParamsDialog` và render lại biểu đồ.
2. **2D Parameter Heatmap (Bản đồ nhiệt Tham số)**:
   - Trục X: Tham số 1 (VD: EMA Fast).
   - Trục Y: Tham số 2 (VD: EMA Slow).
   - Màu sắc ô: Biểu thị Net PnL hoặc Sharpe Ratio (Xanh lá = Tốt, Đỏ = Xấu).
   - Giúp nhận diện vùng tham số ổn định (Plateau).
