# BUG-117 — Bảng Vị thế "đứng hình": unrealized PnL không đổi giữa hai lần khớp lệnh, dù giá vẫn chạy

**Reported date:** 2026-09-10
**Severity:** 🟡 P3 — không sai dữ liệu (số hiển thị từng đúng tại thời điểm
lấy), nhưng gây hiểu nhầm số dư/PnL thật khi người dùng nhìn vào lúc không
có lệnh khớp mới.
**Status:** ✅ Đã sửa 2026-09-10 — root-caused, redesigned (không hotfix),
regression-tested, verified.
**Found by:** user tự chạy app thật trên Testnet, đối chiếu ảnh chụp Binance
UI thật (PNL +15,98 USDT) với số app hiển thị (+2,57 USDT), nghi socket
không nhận dữ liệu.

---

## 1. Symptom

Ảnh chụp Binance UI thật: vị thế ETHUSDT Perp 20x, Size 4.804 ETH, Entry
2436.72, Mark 2440.00, PNL(ROI%) = **+15.98 USDT** (+2.72%).

Cùng lúc, header Dev Board của app hiển thị **+2.57 USDT** cho đúng vị thế
đó — không đổi qua nhiều giây trong khi biểu đồ live vẫn chạy giá thật.

User nghi "socket không fetch data". Không phải — `ACCOUNT_UPDATE` log ở
mức `DEBUG` (từ `BUG-095`/`BUG-113`) nên không xuất hiện trong log INFO user
gửi dù socket hoạt động bình thường.

## 2. Root cause

`FuturesUserDataStream._handle_account_update()` là **nơi duy nhất**
`LivePosition` (mark price, unrealized PnL) của một vị thế được tính lại —
và nó chỉ chạy khi sàn đẩy một `ACCOUNT_UPDATE` (khớp lệnh, funding
settlement). Không có đường nào khác cập nhật nó: tick giá live
(`MarketTickEvent`/`_handle_market_tick`) chỉ vẽ lại chart, không chạm tới
bảng Vị thế. Vì vậy giữa hai lần khớp lệnh, số mark price/PnL hiển thị đứng
yên đúng tại giá trị của lần `ACCOUNT_UPDATE` gần nhất, trong khi giá thị
trường (và PnL thật) vẫn di chuyển liên tục.

Số đo được: mark price app giữ 2437.26 (khớp `(2437.26-2436.72)×4.804 ≈
2.59`, đúng số app hiển thị) trong khi mark price thật lúc chụp ảnh là
2440.00 (`(2440.00-2436.72)×4.804 ≈ 15.76`, khớp số Binance hiển thị).

## 3. Fix

**Bản đầu (bị từ chối — xem `fix-bug-rule.md` §2, "không hotfix"):** một
`QTimer` trong từng Presenter (Trading, Dev Board), tự poll
`GetOpenPositionsQuery` rồi gọi thẳng vào bảng của riêng màn đó. Sửa đúng
triệu chứng nhưng là **2 timer độc lập** cùng gọi một endpoint, và màn thứ
ba trong tương lai sẽ cần thêm một bản sao thứ ba — đúng lớp trùng lặp
`OrderFeed`/`EquityFeed`/`HealthCheckCoordinator`/`LiveOrderBookCoordinator`
đã tồn tại để xoá bỏ.

**Bản sửa thật:** một `PositionRefreshService` duy nhất
(`src/application/services/position_refresh_service.py`), đăng ký **một
lần** lúc boot (`binance_bot_module.py::boot()`) qua `Scheduler` sẵn có của
engine (`scheduler.every(seconds=5).do(refresh_service.refresh_once)`) —
không phải một object mới dựng riêng cho từng màn hình. `refresh_once()`:

- No-op khi `TradingSessionState.enabled` là `False` — tự canh trạng thái,
  không cần `EnableTradingCommand`/`DisableTradingCommand`/
  `EmergencyStopCommand` gọi start()/stop() nào cả.
- Gọi lại đúng `GetOpenPositionsQuery` (không tính field nào cục bộ —
  `LivePosition`'s own docstring: "this app never computes any of its
  fields, only parses them off the wire").
- Phát lại qua **đúng** `PositionChangedEvent`/`PositionClosedEvent` mà
  `OrderFeed` ở CẢ HAI màn đã lắng nghe sẵn từ trước (`_on_position_changed`
  → `LiveOrderBookCoordinator.on_position_changed`) — 0 dòng wiring mới ở
  Presentation layer, màn thứ ba trong tương lai được lợi miễn phí.

Một poll, N màn hình — không phải N poll độc lập.

**Theo yêu cầu review tiếp theo của user** ("5s mới GetOpenPositionsQuery 1
lần sao, để nó vào cơ chế config đi, có giới hạn thấp nhất theo spec của
Binance nhé") — chu kỳ 5s không còn hard-code:

- `ConfigKeys.TRADING_POSITION_REFRESH_INTERVAL_SECONDS` (`trading.
  position_refresh_interval_seconds`) — đọc qua `IConfig`, mặc định vẫn
  5.0s.
- `BinanceBotModule._MIN_POSITION_REFRESH_INTERVAL_SECONDS = 1.0` — sàn
  chặn dưới. `futures_position_information()` (`python-binance`) gọi đúng
  endpoint Binance tài liệu hoá "Position Information V3"
  (`GET /fapi/v3/positionRisk`), weight 5 theo bảng weight USDⓈ-M Futures
  API công khai của Binance (**chưa re-verify qua lệnh gọi thật** — egress
  `*.binance.*` bị chặn trong sandbox, cùng disclosure
  `futures_account_reader.py` đã ghi). Ngân sách weight mặc định theo IP
  là 2400/phút; ở 1 lần/giây, riêng poll này tốn `60 × 5 = 300` weight/phút
  (12,5% ngân sách đó) — còn đủ chỗ cho mọi request khác của app. Một giá
  trị config dưới ngưỡng này bị nâng lên đúng ngưỡng, kèm 1 dòng log
  `WARNING` nêu rõ key + giá trị bị nâng (không âm thầm bỏ qua).

## 4. Regression test

`tests/unit/application/services/test_position_refresh_service.py` (5
test): no-op khi tắt trading; dispatch + publish `PositionChangedEvent` khi
bật; publish `PositionClosedEvent` cho symbol không còn xuất hiện ở lần
fetch sau; một lỗi dispatch không văng exception; tắt trading giữa chừng
dừng hẳn các lần dispatch tiếp theo.

`tests/unit/test_binance_bot_module_position_refresh_interval.py` (4
test, thêm theo yêu cầu review về config): không có config → mặc định
5.0s; giá trị trên ngưỡng được giữ nguyên; giá trị dưới ngưỡng bị nâng lên
đúng `_MIN_POSITION_REFRESH_INTERVAL_SECONDS`; việc nâng lên có log
`WARNING` nêu tên key.

## 5. Xác minh

- `pytest tests/unit/application/services/test_position_refresh_service.py`: 5 passed.
- `pytest tests/integration/test_app_integration.py`: 1 passed — app vẫn boot đúng với wiring mới.
- `ruff check`/`ruff format --check` sạch trên mọi file đã sửa.
- CI gate đầy đủ (`ci-local.ps1 -Full`) chạy sau khi sửa, xác nhận bằng grep log file thật.

## 6. Ghi chú quy trình

Bản đầu (per-screen `QTimer`) đã bị user chặn lại đúng lúc ("ko hot fix
nhé, cần thiết thì phải design lại cơ chế để có thế scalable") — root cause
đúng, fix đúng triệu chứng, nhưng sai tầm kiến trúc: vá tại từng điểm gọi
thay vì sửa cơ chế dùng chung. Đã redesign theo đúng yêu cầu, và ghi thành
luật thường trực ở `fix-bug-rule.md` §2 (mới) để không lặp lại lớp lỗi này.
