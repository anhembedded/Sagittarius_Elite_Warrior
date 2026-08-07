# Nhiệm vụ: Concrete Strategy + Buy/Sell Signal Markers trên Dev Board

## 1. Mục tiêu (Objective)
Xây dựng chiến lược giao dịch cụ thể đầu tiên (vd. EMA Crossover) dùng `StrategyEngine` đã có từ `BOT-020`, hiển thị tín hiệu Buy/Sell lên Dev Board — cả log ở System Monitor lẫn marker trực quan trên chart — theo đúng cơ chế batch/incremental liên tục đã dùng cho Indicator Control Card (`Load History` chạy batch, live tick tiếp tục đúng state).

## 2. Bối cảnh (Context)
Khi làm tính năng Indicator Control Card (hiển thị RSI/EMA/MACD lên Dev Board), user chủ động hoãn phần strategy: *"chưa có indicator cho dev board... chưa cần strategy bây giờ"*. `BOT-020` đã xây xong lõi (`IStrategy` protocol + `StrategyEngine`) nhưng **cố tình chưa ship concrete strategy nào** — task này là bước tiếp theo tự nhiên, tái sử dụng toàn bộ lõi đó thay vì làm lại.

## 3. Các bước thực hiện (Action Items)
- [ ] Cài đặt ít nhất 1 `IStrategy` cụ thể (vd. `EmaCrossoverStrategy`: fast EMA cắt lên slow EMA → BUY, cắt xuống → SELL, còn lại → HOLD) — tái sử dụng `EMA` từ `domain/indicators/`, không viết lại phép tính.
- [ ] Thêm UI chọn/chỉnh chiến lược — cân nhắc tái sử dụng dropdown "Strategy" hiện có trong `ControlCard` (hiện đang là UI tĩnh, chưa có logic phía sau) thay vì tạo control mới.
- [ ] Nối `StrategyEngine` vào `DashboardPresenter`, đi theo đúng pattern đã dùng cho indicator (batch khi `Load History`, tiếp tục incremental khi có live tick, dùng chung 1 `StrategyEngine` instance qua cả 2 chế độ nhờ thiết kế batch=replay-of-incremental của `BOT-020`).
- [ ] Log mỗi tín hiệu Buy/Sell ra System Monitor (định dạng tương tự các dòng `[User clicked ...]` đã có — vd. `[Strategy] BUY ETHUSDT @ 1875.37 (EMA crossover)`).
- [ ] Vẽ marker Buy/Sell lên chart tại đúng nến phát tín hiệu — `ChartCard`/`IndicatorManager` hiện **chưa có API vẽ marker/annotation** (chỉ có `add_overlay`/`add_subplot` cho đường line), cần thêm khả năng mới (vd. `pg.ScatterPlotItem` với glyph tam giác lên/xuống, màu theo action).
- [ ] Quyết định phạm vi symbol — giữ đúng giả định single-symbol của Dev Board hiện tại (khớp `BOT-014` và Indicator Control Card vừa làm), không mở rộng multi-symbol trong task này.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đây là **concrete `IStrategy` đầu tiên** trong codebase — `BOT-020` cố tình không ship cái nào, nên không có ví dụ sẵn để bắt chước, cần tự thiết kế từ đầu (nhưng bám sát docstring của `IStrategy`: `Signal.time`/`price` phải lấy từ `context.candle`, không dùng wall-clock, để giữ đúng tính chất "batch và incremental luôn khớp kết quả" mà `BOT-020` đã đảm bảo).
- Marker vẽ trên chart là tín hiệu **chiến lược** (StrategyEngine), khác với "Trade Markers Manager" từng bị hoãn ở `BOT-010` (task đó vẽ marker từ `OrderFilledEvent` thật — tức lệnh đã khớp trên sàn). Hai khái niệm marker này độc lập nhau — task này KHÔNG cần chờ `BOT-008`/order execution thật.
- Không mở rộng sang `ExecuteOrderCommand`/đặt lệnh thật — đó là phạm vi của `BOT-008`. Task này chỉ dừng ở hiển thị tín hiệu trên Dev Board.

## 5. Phụ thuộc (Dependencies)
- `BOT-020` ✅ (Indicator & Strategy Engine Core) — bắt buộc, tái sử dụng toàn bộ `StrategyEngine`/`IStrategy`/`Signal`.
- Tham khảo cách nối indicator vào `DashboardPresenter` (Load History batch + live tick incremental) đã làm ngay trước task này, trong cùng file `dashboard_presenter.py`.
