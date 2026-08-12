# Nhiệm vụ: Chiến lược QML Structure Breakout

> Thuộc [BOT-043](BOT-043_named_strategy_library.md), Epic
> [BOT-040](BOT-040_backtest_screen_full_feature_epic.md).
> Phụ thuộc `BOT-026` ✅, [`BOT-046`](BOT-046_strategy_param_plumbing.md).
> **Độ khó: cao** — nhận diện price-action pattern, không phải phép tính chỉ
> báo.

## 1. Mục tiêu

Nhận diện mẫu hình **QML (Quasimodo)** trên cấu trúc giá và vào lệnh khi mẫu
hình được xác nhận (breakout). Mockup của user cho thấy chiến lược này sinh ra
2 thứ mà các chiến lược khác không có:

- **"QML Signal Score: 92/100"** — điểm chất lượng mẫu hình, hiện trong dòng
  mở rộng của bảng Trade Logs.
- **"Độ nhạy Mẫu hình QML (Score %)" = 85** — tham số ngưỡng trong modal cấu
  hình: chỉ vào lệnh khi score ≥ ngưỡng.
- **"QML Signal Badges"** — nhãn trên chart (toggle riêng trong Chart Canvas).
- Lý do vào lệnh dạng văn xuôi: *"QML Liquidity Sweep + EMA 21 Resistance"*.

## 2. ⚠️ Phần khó nhất: định nghĩa mẫu hình — KHÔNG tự suy diễn

QML/Quasimodo là mẫu hình price-action có định nghĩa cụ thể trong giới
trading (một biến thể của vai-đầu-vai, dựa trên chuỗi đỉnh/đáy và việc phá
cấu trúc). **Không code trước khi có định nghĩa chính xác từ user**, vì:

- Hiểu sai 1 chi tiết → chiến lược mang đúng tên nhưng logic sai. User sẽ tin
  vào kết quả backtest của nó để ra quyết định giao dịch thật.
- Không có "gần đúng" ở đây: mẫu hình hoặc đúng định nghĩa, hoặc là một mẫu
  hình khác.

Cần user cung cấp rõ:
- Quy tắc xác định các đỉnh/đáy cấu thành mẫu hình (swing high/low tính thế
  nào? bao nhiêu nến 2 bên?).
- Điều kiện xác nhận breakout.
- **Công thức tính "QML Score" 0-100** — đây là chỉ số do chiến lược tự định
  nghĩa, không có chuẩn chung.

## 3. Các bước thực hiện (Action Items)

- [ ] Lấy định nghĩa đầy đủ từ user (mục 2), viết vào docstring trước khi code.
- [ ] **Hạ tầng còn thiếu: phát hiện swing high/low.** `domain/scripting/`
  hiện có `Series` (lịch sử giá trị) + cross helpers, nhưng **không có** công
  cụ nào tìm đỉnh/đáy cục bộ — đây là nền tảng của mọi phân tích cấu trúc giá.
  Thêm helper **dùng chung** vào `domain/scripting/` (đúng vai trò thư mục
  này, và mọi chiến lược price-action sau này đều cần) thay vì viết riêng
  trong strategy. Xem [`BOT-043`](BOT-043_named_strategy_library.md) mục 3.
- [ ] ⚠️ **`Series` mặc định chỉ giữ 16 bar — nhiều khả năng không đủ cho
  phân tích cấu trúc.** `DEFAULT_HISTORY = 16` (`src/domain/scripting/series.py`)
  được chọn có chủ đích cho lookback ngắn của indicator script — docstring ghi
  rõ *"crossovers need 2; a few formulas compare against 3-5 bars back […]
  Pine keeps everything, we deliberately don't"*, tức đánh đổi có ý thức để bộ
  nhớ không phình theo độ dài backtest. Nhưng mẫu hình Quasimodo cần nhìn xa
  hơn nhiều bar. `Series` **đã hỗ trợ** `Series(history=N)` nên trước mắt
  truyền giá trị lớn hơn ở chỗ cần — nhưng phải **đánh giá thực tế bao nhiêu
  là đủ**, và cân nhắc cách lưu trữ hiện tại (deque cố định) có phù hợp không.
- [ ] `QmlStructureBreakoutStrategy(BaseStrategy)` + input "độ nhạy score"
  (default 85 theo mockup).
- [ ] Gắn `metadata={"qml_score": ...}` vào `Signal`
  ([`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md)) để bảng Trade
  Logs hiện được "QML Signal Score: 92/100".
- [ ] Lý do vào lệnh (`Signal.reason`) mô tả đúng bối cảnh, kiểu *"QML
  Liquidity Sweep + EMA 21 Resistance"* — không phải chuỗi chung chung.
- [ ] Test: dựng chuỗi giá **có mẫu hình QML rõ ràng** (tính tay theo định
  nghĩa) → chiến lược nhận ra; dựng chuỗi **gần giống nhưng thiếu 1 điều
  kiện** → **không** nhận ra. Test thứ hai quan trọng hơn test thứ nhất.
- [ ] Test ngưỡng score: mẫu hình có score dưới ngưỡng → không vào lệnh.

## 4. Phụ thuộc

- `BOT-026` ✅, [`BOT-046`](BOT-046_strategy_param_plumbing.md),
  [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md).
- Chart Canvas ([`BOT-056`](../completed/BOT-056_backtest_chart_canvas.md)) — nơi vẽ "QML
  Signal Badges".
