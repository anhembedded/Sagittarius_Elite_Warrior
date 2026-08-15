# Nhiệm vụ: Trade Journal Detail — Lý do vào/thoát lệnh & metadata theo chiến lược

> Thuộc [Epic BOT-040](../backlog/BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> Chặn phần "dòng mở rộng" của bảng Trade Logs trong spec UI. Phụ thuộc
> `BOT-021` ✅ (`Trade`/`PaperExchange`), `BOT-026` ✅ (`Signal.reason`).

## 1. Mục tiêu

Mỗi dòng lệnh trong bảng Trade Logs mở rộng ra được 3 khối thông tin (theo
mockup user cung cấp, dòng `#216 lệnh bán`):

| Khối trong mockup | Ví dụ giá trị | Nguồn dữ liệu |
| :--- | :--- | :--- |
| **LÝ DO VÀO LỆNH** (Entry Catalyst) | "QML Liquidity Sweep + EMA 21 Resistance" | `Signal.reason` lúc mở vị thế |
| **LÝ DO THOÁT LỆNH** (Exit Execution) | "Chạm Stop Loss (SL)" | `PaperExchange` — lý do đóng vị thế |
| **CHỈ SỐ ĐÁNH GIÁ & THỜI LƯỢNG** | "QML Signal Score: 92/100" · "Thời lượng: 4h 00m" | metadata do strategy tự gắn + tính từ `entry_time`/`exit_time` |

User nhấn mạnh: **"tùy vào chiến thuật"** — tức khối thứ 3 không phải tập cột
cố định; mỗi chiến lược gắn được chỉ số riêng của nó (QML Score chỉ có nghĩa
với chiến lược QML), UI hiển thị bất cứ gì strategy cung cấp.

## 2. Đối chiếu code hiện có — gap cụ thể

**Đã có sẵn (tin tốt)**: `Signal` (`domain/value_objects/signal.py`) **đã có
field `reason: str`**, và `BaseStrategy.buy()/sell()/hold()` (`BOT-026`) đã
bắt subclass truyền lý do dạng văn xuôi (vd `EmaCrossoverStrategy` trả
`"EMA Crossover 3/5 crossed above"`). Nguồn dữ liệu cho "Lý do vào lệnh" **đã
tồn tại**, chỉ là chưa được giữ lại.

**Gap thật**:

1. `PaperExchange._open()` nhận `Signal` qua `fill()` nhưng **vứt bỏ
   `signal.reason`** — `_OpenPosition` không lưu, nên tới lúc `_close()` dựng
   `Trade` thì không còn lý do vào lệnh nữa.
2. `Trade` (`domain/backtesting/trade.py`) **không có** `entry_reason`/
   `exit_reason`/metadata.
3. **Không có khái niệm "lý do thoát"** — `PaperExchange` hiện chỉ đóng vị thế
   bằng đúng 2 đường (tín hiệu SELL, hoặc `force_close()` cuối backtest) và
   không phân biệt chúng trong kết quả. Mockup cần phân biệt ít nhất:
   tín hiệu chiến lược / chạm SL / chạm TP / thanh lý (liquidation) / kết thúc
   backtest. **SL/TP/liquidation chưa tồn tại — thuộc `BOT-041`**, nên task
   này cần thiết kế enum lý do thoát sao cho `BOT-041` thêm vào được mà không
   phải sửa lại `Trade`.
4. **Không có chỗ cho metadata theo chiến lược** — `Signal` không có field mở
   rộng, nên strategy không có đường nào gắn "QML Score: 92/100" vào lệnh.

## 3. Các bước thực hiện (Action Items)

- [x] Thêm `metadata: Mapping[str, Any]` (default rỗng) vào `Signal` — chỗ để
  strategy gắn chỉ số riêng. Dùng `Mapping` + default factory rỗng để giữ
  `Signal` vẫn `frozen=True` và không phá mọi chỗ đang dựng `Signal` (kể cả
  test suite `test_strategy_engine.py` đang pin — **không được sửa file đó**,
  xem mục 4).
- [x] `BaseStrategy.buy()/sell()/hold()` nhận thêm metadata optional, để
  `decide()` viết được `return self.buy("QML Liquidity Sweep", score=92)` mà
  không cần tự dựng `Signal`.
- [x] `_OpenPosition` lưu `entry_reason` + `entry_metadata` từ `Signal` lúc
  `_open()`.
- [x] Enum/`StrEnum` lý do thoát: `STRATEGY_SIGNAL`, `END_OF_BACKTEST` (2 cái
  hiện có); chừa sẵn `STOP_LOSS`, `TAKE_PROFIT`, `LIQUIDATION` cho `BOT-041`
  điền vào sau — khai báo trước cả 5 để `BOT-041` không phải đổi kiểu dữ liệu
  `Trade`.
- [x] `Trade` thêm: `entry_reason: str`, `exit_reason: <enum>`,
  `metadata: Mapping[str, Any]`. **Không** thêm field `duration` — tính được
  từ `exit_time - entry_time`, thêm field là dữ liệu trùng lặp có thể lệch.
- [x] `PaperExchange.force_close()` gắn `END_OF_BACKTEST`, đường SELL thường
  gắn `STRATEGY_SIGNAL`.
- [x] UI (thuộc `BOT-022`/`BOT-057`): dòng mở rộng hiển thị 3 khối; khối
  metadata render động theo key có mặt (không hardcode "QML Score"), thời
  lượng format kiểu "4h 00m". Đóng luôn §2.2 của `BOT-057` — xem file đó.
- [x] Test: 1 lệnh đóng bằng tín hiệu và 1 lệnh đóng bằng `force_close()` cho
  ra đúng 2 `exit_reason` khác nhau; `entry_reason` khớp đúng `Signal.reason`
  của lệnh mở (không phải của lệnh đóng — dễ nhầm).

## 6. Ghi chú triển khai thực tế

Toàn bộ 8 action item ở mục 3 đã làm đúng như thiết kế, không có gì phải đảo
ngược:

- `ExitReason(str, Enum)` sống ở `domain/backtesting/exit_reason.py` — cả 5
  member khai báo ngay từ đầu như dự tính, `BOT-041`/`BOT-049` chỉ cần bắt đầu
  *phát ra* `STOP_LOSS`/`TAKE_PROFIT`/`LIQUIDATION`, không phải sửa kiểu dữ
  liệu `Trade` hay bảng dịch nhãn tiếng Việt trong `trade_log_row.py`.
- `BaseStrategy.buy()/sell()/hold()` nhận `**metadata: Any` (không phải dict
  tường minh) — cho phép `return self.buy("QML Liquidity Sweep", score=92)`
  đúng như ví dụ trong task; `decide()` đổi kiểu trả về sang
  `tuple[SignalAction, str, Mapping[str, Any]]`, `evaluate()` unpack 3 phần
  tử và gắn vào `Signal.metadata`.
- `EmaCrossoverStrategy` — chỉ đổi type annotation của `decide()` cho khớp,
  **0 dòng logic thay đổi** (thân hàm vẫn gọi `self.buy(...)`/`self.sell(...)`
  nguyên vẹn), nên không tạo metadata nào — đúng thực tế "chưa chiến lược nào
  cần metadata hôm nay".
- `Trade`/`Signal` cả 3 field mới (`entry_reason`/`exit_reason`/`metadata`)
  đều có default (`""`/`ExitReason.STRATEGY_SIGNAL`/`{}`) dù task không bắt
  buộc — cần thiết để giữ nguyên ~9 file test đang dựng `Trade(...)` bằng
  keyword args mà không phải sửa tay từng file.
- **UI đã làm luôn**, không để lại cho `BOT-022`: `BackTestTradeLogs.qml` mỗi
  dòng giờ là `Button` (bấm để mở rộng, không phải `Rectangle+MouseArea` —
  giữ đúng quy ước "phải click test được từ Python" đã đúc kết ở `BOT-057`) +
  1 `Rectangle` chi tiết ẩn/hiện theo `root.expandedRows[trade.index]` (JS
  object, thay toàn bộ khi toggle vì QML chỉ phản ứng khi gán lại nguyên
  giá trị). 3 khối: Lý do vào lệnh / Lý do thoát lệnh / Chỉ số & thời lượng
  (`Repeater` trên `metadataItems`, key nào có thì hiện, không hardcode).
- CSV export (`trade_log_export.py`) thêm 3 cột `entry_reason`/`exit_reason`/
  `metadata` (metadata serialize JSON) — theo đúng nguyên tắc gốc của
  `BOT-057`: export phải đầy đủ hơn bảng hiển thị trên màn hình.
- 15 test mới xuyên domain→presentation→QML (`test_paper_exchange.py`,
  `test_base_strategy.py` mới, `test_trade_log_row.py`, `test_trade_log_export.py`,
  `test_backtest_presenter.py` — bao gồm test click thật mở/đóng dòng chi
  tiết), 643 test toàn `tests/unit/` + `tests/sanity/` pass, `ruff` sạch.

## 4. Rủi ro / Lưu ý

- **Bất biến bắt buộc giữ**: `tests/unit/application/services/test_strategy_engine.py`
  (`BOT-020`, 180 dòng) và `src/application/services/strategy_engine.py` đang
  là vùng "diff = 0 dòng" đã cam kết từ `BOT-026`. Mọi field mới trên `Signal`
  **phải có default** để 2 file đó không phải sửa 1 dòng nào.
- `Mapping[str, Any]` là cái giá phải trả cho "tùy vào chiến thuật" — không
  type-safe. Chấp nhận có chủ đích: tập chỉ số là mở theo chiến lược, ép
  schema cứng sẽ chặn đúng thứ user muốn. Bù lại: UI phải chịu được key lạ/
  thiếu mà không crash.
- Thứ tự làm hợp lý: task này **trước** `BOT-041` (để `BOT-041` sinh SL/TP có
  sẵn chỗ ghi `exit_reason`), hoặc gộp chung nếu làm liền tay.

## 5. Phụ thuộc

- `BOT-021` ✅ — `Trade`/`PaperExchange`.
- `BOT-026` ✅ — `Signal.reason`, `BaseStrategy.buy()/sell()`.
- `BOT-041` — điền nốt `STOP_LOSS`/`TAKE_PROFIT`/`LIQUIDATION`.
- `BOT-043` — chiến lược QML mới là nơi thực sự sinh ra "QML Signal Score".
