# Nhiệm vụ: Chiến lược 4 EMA Pullback + Sideways Filter

> Thuộc [BOT-043](BOT-043_named_strategy_library.md), Epic
> [BOT-040](BOT-040_backtest_screen_full_feature_epic.md).
> Phụ thuộc `BOT-026` ✅, [`BOT-046`](../completed/BOT-046_strategy_param_plumbing.md).
> **Độ khó: trung bình.** Đây là chiến lược xuất hiện trong tiêu đề modal của
> mockup user cung cấp ("4 EMA PULLBACK + SIDEWAYS FILTER + QML"), nên nhiều
> khả năng là chiến lược user quan tâm nhất.

## 1. Mục tiêu

Vào lệnh khi giá **hồi về** (pullback) một trong các đường EMA trong xu hướng
đang chạy — nhưng **lọc bỏ** tín hiệu khi thị trường đi ngang (sideways), vì
pullback trong sideways là tín hiệu giả.

## 2. Phần khó thật: định nghĩa "sideways" bằng số liệu

Codebase **chưa có khái niệm nào** về trạng thái thị trường. Cần chốt cách đo,
mỗi cách cần indicator khác nhau:

- **ATR thấp** — biến động nhỏ so với trung bình. Cần `ATR` (**chưa có** trong
  `domain/indicators/` — hiện chỉ có EMA/RSI/MACD/WMA → phải viết mới).
- **Các EMA đan xen nhau** — khoảng cách giữa các EMA nhỏ hơn ngưỡng. Dùng
  được indicator đã có, không cần viết mới.
- **ADX thấp** — chỉ báo sức mạnh xu hướng chuyên dụng (**chưa có**, phải viết
  mới, phức tạp hơn ATR).

**Không tự chọn** — hỏi user. Nếu chọn ATR/ADX thì phát sinh thêm việc viết
indicator mới (cần test riêng, đối chiếu công thức chuẩn).

## 3. Cần chốt trước khi code

- 4 EMA period mặc định là gì? (mockup chỉ hiện "EMA Fast / Slow = 8 / 21")
- "Pullback" định nghĩa thế nào: giá **chạm** EMA, **xuyên qua rồi đóng lại
  trên**, hay **nằm trong vùng** giữa 2 EMA?
- Cách đo sideways (mục 2) + ngưỡng.
- Thoát lệnh bằng gì: tín hiệu ngược, hay để SL/TP
  ([`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md)) lo?

## 4. Các bước thực hiện (Action Items)

- [ ] Chốt toàn bộ mục 2 + 3 với user, viết định nghĩa rõ ràng vào docstring
  **trước** khi code.
- [ ] Nếu chọn ATR/ADX: viết indicator mới trong `domain/indicators/` theo
  đúng khuôn `IIndicator` (stateful, `update(value) -> T | None`, warm-up trả
  `None`), test đối chiếu công thức chuẩn. **Lưu ý**: `IIndicator.update()`
  hiện chỉ nhận **1 float** (close price) — ATR cần cả high/low/close, nên
  đây là **hạn chế kiến trúc thật** cần giải quyết (mở rộng interface hoặc
  đường riêng cho indicator đa-input). Đánh giá kỹ trước khi cam kết.
- [ ] `FourEmaPullbackStrategy(BaseStrategy)` với input cho 4 period + ngưỡng
  sideways.
- [ ] Gắn metadata (vd "trạng thái thị trường: trending/sideways") vào
  `Signal` cho bảng Trade Logs.
- [ ] Test: có ít nhất 1 kịch bản mà **bộ lọc sideways chặn được tín hiệu**
  mà nếu không có lọc thì sẽ vào lệnh — chứng minh bộ lọc thực sự hoạt động,
  không phải code chết.
- [ ] Test golden signal list + batch ≡ incremental.

## 5. Rủi ro / Lưu ý

- **`IIndicator` chỉ nhận 1 giá trị** (`update(value: float)`) — nếu chọn ATR
  (cần H/L/C) thì đụng giới hạn kiến trúc, không phải việc nhỏ. Cân nhắc chọn
  cách đo sideways bằng khoảng cách EMA (chỉ cần close) để tránh, nếu user
  không có yêu cầu cụ thể.

## 6. Phụ thuộc

- `BOT-026` ✅, [`BOT-046`](../completed/BOT-046_strategy_param_plumbing.md).
- [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md) — metadata.
