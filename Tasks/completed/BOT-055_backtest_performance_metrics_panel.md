# Nhiệm vụ: Backtest Screen — Performance Metrics Panel (stat cards)

> **Task 2/4** của màn Backtest: [`BOT-022`](BOT-022_backtest_screen_static_ui.md)
> → `BOT-055` (file này) → [`BOT-056`](BOT-056_backtest_chart_canvas.md) →
> [`BOT-057`](BOT-057_backtest_trade_logs_table.md).
> Thuộc Epic [BOT-040](../backlog/BOT-040_backtest_screen_full_feature_epic.md).
> Phụ thuộc [`BOT-022`](BOT-022_backtest_screen_static_ui.md), `BOT-021` ✅.

## 1. Mục tiêu

4 stat card chính + chỗ mở rộng, đọc từ `BacktestResult.metrics`
(`BacktestMetrics`, đã có đủ 13 chỉ số từ `BOT-021`).

## 2. Các bước thực hiện (Action Items)

- [ ] **Net PnL** — `net_profit` + `net_profit_percent` (mockup: "+4,352.11
  USD" / "+435.21%").
- [ ] **Max Drawdown** — `max_drawdown_percent` có sẵn; **số tiền tuyệt đối**
  tại đáy drawdown tính ở UI từ `equity_curve` (mockup: "1,301.47 USD /
  -36.36%"). Không sửa `BacktestMetrics`.
- [ ] **Win Rate** — `percent_profitable` + đếm thắng/tổng từ `result.trades`
  ở UI (mockup: "72.34%" · "34/47 lệnh").
- [ ] **Profit Factor** — `profit_factor`. ⚠️ Giá trị có thể là
  `float("inf")` (khi không có lệnh thua — `BacktestMetrics` trả đúng như
  vậy có chủ đích); hiển thị "∞" thay vì để crash format số.
- [ ] Màu theo dấu (lãi xanh / lỗ đỏ) — dùng `BULL_COLOR`/`BEAR_COLOR` từ
  `chart_card/theme.py`, không định nghĩa màu mới.
- [ ] Tái sử dụng `BaseCard` (`sagittarius_engine.pyside_mvc`) cho khung card.
- [ ] Nút **"Mở rộng chỉ số chi tiết"** — hiển thị nốt các chỉ số còn lại đã
  có trong `BacktestMetrics` (Gross Profit/Loss, Avg Trade, Avg/Largest
  Win/Loss, Total Closed Trades).
- [ ] Unit test: `BacktestResult` giả lập → card hiện đúng số; ca
  `profit_factor = inf`; ca 0 trade (mọi card về 0, không crash).

## 3. ❓ Sharpe / Sortino / Payoff ratio — chưa có, cần chốt công thức

Spec nhắc tới trong phần "mở rộng chỉ số". `BacktestMetrics` **chưa có** 3 chỉ
số này. Sharpe/Sortino cần:
- Chuỗi return theo **kỳ nào** (theo ngày? theo lệnh?) — cho ra kết quả khác
  hẳn nhau.
- **Risk-free rate** giả định (thường 0 với crypto, nhưng phải nói rõ).

Việc code nhỏ, nhưng **chọn sai công thức thì con số sai mà vẫn trông hợp
lý** — không tự chọn, hỏi user khi làm tới. Payoff ratio (`avg_win /
|avg_loss|`) thì đơn giản và không mơ hồ, làm được ngay từ dữ liệu đã có.

## 4. Phụ thuộc

- [`BOT-022`](BOT-022_backtest_screen_static_ui.md) — khung màn hình.
- `BOT-021` ✅ — `BacktestMetrics`.
