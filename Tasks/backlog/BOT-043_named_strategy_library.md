# Epic con: Named Strategy Library — chiến lược trong dropdown

> Thuộc [Epic BOT-040](BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Đây là file chỉ mục** — mỗi chiến lược là 1 task riêng (chia nhỏ theo yêu
> cầu user), vì độ khó chênh nhau rất xa. Phụ thuộc `BOT-026` ✅,
> [`BOT-046`](BOT-046_strategy_param_plumbing.md) (để có tham số).

## 1. Danh sách task

| Task | Chiến lược | Độ khó | Vì sao |
| :--- | :--- | :---: | :--- |
| [`BOT-051`](BOT-051_multi_ema_trend_follower.md) | Multi-EMA Trend Follower | Thấp | Gần giống `EmaCrossoverStrategy` đã có, chỉ nhiều đường EMA hơn. |
| [`BOT-052`](BOT-052_four_ema_pullback_sideways_filter.md) | 4 EMA Pullback + Sideways Filter | Trung bình | Cần định nghĩa "sideways" bằng số liệu — chưa có khái niệm này trong codebase. |
| [`BOT-053`](BOT-053_qml_structure_breakout.md) | QML Structure Breakout | Cao | Nhận diện **price-action pattern** (Quasimodo) trên chuỗi high/low, không phải phép tính chỉ báo. |

## 2. ⏸️ Đã bỏ khỏi phạm vi: SMC + Liquidity Sweep (cân nhắc lại sau)

Chiến lược **QT Smart Money Concepts (SMC + Liquidity Sweep)** có trong spec
UI gốc nhưng **user đã quyết định bỏ** khỏi kế hoạch hiện tại. Task file
`BOT-054` đã xoá; giữ lại ghi chú ở đây để sau này cân nhắc lại có đủ bối
cảnh, không phải phân tích lại từ đầu:

- SMC **không phải một thuật toán** mà là cả một trường phái phân tích, gồm
  nhiều khái niệm con: **Order Block** (nến cuối trước cú đẩy mạnh — "mạnh"
  là bao nhiêu %?), **Liquidity Sweep / Stop Hunt** (quét qua đỉnh/đáy cũ rồi
  đảo chiều — quét bao xa, đảo trong mấy nến?), **Fair Value Gap (FVG)**,
  **Break of Structure (BOS) / Change of Character (CHoCH)**.
- **Không có định nghĩa chuẩn duy nhất** cho các khái niệm này — mỗi trường
  phái/người dạy một biến thể. Tự chọn một biến thể rồi code sẽ ra chiến lược
  mang tên SMC nhưng không phải cái user hình dung, mà user lại tin vào kết
  quả backtest của nó để giao dịch tiền thật. Đó là lý do chi phí làm **đúng**
  rất cao.
- Nếu quay lại làm: **chốt phạm vi trước** (không cần dùng hết các khái niệm —
  có thể chỉ liquidity sweep + BOS; càng ít càng dễ đúng), lấy định nghĩa bằng
  số liệu cho **từng** khái niệm từ user, và cân nhắc chia mỗi khái niệm thành
  1 task có test riêng.
- Hạ tầng dùng chung với [`BOT-053`](BOT-053_qml_structure_breakout.md):
  swing high/low detection (xem mục 3).

## 3. ⚠️ Hạ tầng còn thiếu cho mọi chiến lược phân tích cấu trúc giá

Hai ghi chú này áp dụng cho `BOT-053` và bất kỳ chiến lược price-action nào
sau này (kể cả SMC nếu quay lại làm):

1. **Chưa có công cụ phát hiện swing high/low.** `domain/scripting/` hiện có
   `Series` (lịch sử giá trị) + cross helpers (`crossed_above`/`crossed_below`/
   `is_above`/`is_below`), nhưng **không có** gì tìm đỉnh/đáy cục bộ — đây là
   nền tảng của mọi phân tích cấu trúc giá. Nên thêm helper **dùng chung** vào
   `domain/scripting/` (đúng vai trò của thư mục này) thay vì viết riêng trong
   từng strategy.

2. **`Series` mặc định chỉ giữ 16 bar — nhiều khả năng không đủ cho phân tích
   cấu trúc.** `DEFAULT_HISTORY = 16` (`src/domain/scripting/series.py`) được
   chọn có chủ đích cho các lookback ngắn mà indicator script thường dùng —
   docstring ghi rõ: *"crossovers need 2; a few formulas compare against 3-5
   bars back […] Pine keeps everything, we deliberately don't"*, tức là đánh
   đổi có ý thức để bộ nhớ không phình theo độ dài backtest. Nhưng mẫu hình
   cấu trúc (Quasimodo, BOS, order block…) cần nhìn xa hơn nhiều bar. `Series`
   **đã hỗ trợ** tham số `history` tuỳ chỉnh (`Series(history=N)`), nên cách
   xử lý trước mắt là truyền giá trị lớn hơn ở chỗ cần — nhưng cần **đánh giá
   thực tế xem bao nhiêu là đủ**, và cân nhắc liệu cách lưu trữ hiện tại
   (deque cố định) có phù hợp cho nhu cầu này không, hay cần cơ chế khác.

## 4. Nguyên tắc chung cho các task chiến lược

- **Không tự suy diễn định nghĩa thuật toán từ tên gọi.** Với `BOT-053` đặc
  biệt: hiểu sai 1 chi tiết sẽ ra chiến lược mang đúng tên nhưng logic sai —
  nguy hiểm hơn là chưa có tính năng, vì user sẽ tin vào kết quả backtest của
  nó. Viết rõ định nghĩa **trước** khi code, xác nhận với user.
- Theo đúng khuôn `BaseStrategy` (`BOT-026`): `decide()` thuần, không tự tính
  indicator, khai báo qua `build_indicators()`.
- Khai báo tham số qua cơ chế input ([`BOT-046`](BOT-046_strategy_param_plumbing.md)).
- Gắn metadata riêng vào `Signal`
  ([`BOT-045`](BOT-045_trade_journal_detail_and_metadata.md)) để bảng Trade
  Logs hiển thị chỉ số đặc thù (vd "QML Signal Score 92/100").

## 5. Không chặn gì

Dropdown chiến lược hoạt động đúng với 1 entry (`ema_crossover`) đã có. Thêm
chiến lược chỉ cần `.register()`, **không cần sửa UI**. Làm task nào trước
tuỳ nhu cầu thật của user.
