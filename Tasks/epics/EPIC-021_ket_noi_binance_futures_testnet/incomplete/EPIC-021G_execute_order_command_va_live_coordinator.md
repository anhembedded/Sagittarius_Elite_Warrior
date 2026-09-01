# EPIC-021G — `ExecuteOrderCommand` + `LiveTradingCoordinator`: lệnh thật đầu tiên

- **Trạng thái:** 🔴 Chưa bắt đầu
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021F` · **Chặn:** `EPIC-021H`

---

## 1. Bối cảnh & vấn đề thật

Đây là task nối tín hiệu với sàn — và là task duy nhất trong epic có thể tạo ra một lệnh khớp
thật.

Hôm nay đường live dừng ở một dòng log: `MarketTickEventHandler.handle()` in ra
*"Processing tick for {symbol} at {price}"* rồi return, kèm comment
*"Here we will later invoke domain logic for strategy processing"*
([`market_tick_event_handler.py`](../../../../src/application/event_handlers/market_data/market_tick_event_handler.py)).
`StrategyEngine` đã có `on_tick()` và đã sinh `SignalGeneratedEvent`, nhưng **chỉ backtest handler
gọi nó** — luồng live chưa bao giờ chạy qua.

Rủi ro thật của task này không phải "lệnh sai một chút". Là **một vòng lặp tín hiệu bắn hàng trăm
lệnh**. Trên testnet mất tiền giả; nhưng cùng đoạn code đó là thứ sau này chạy trên tiền thật, và
một hạn mức thêm sau bao giờ cũng thiếu một đường vòng.

## 2. Thiết kế + lý do

### 2.1 Use case CQRS, không phải handler tự gọi adapter

```
src/application/use_cases/trading/execute_order/{command.py,handler.py,__init__.py}
```

`MarketTickEventHandler` chạy `StrategyEngine.on_tick()`; tín hiệu actionable phát
`SignalGeneratedEvent`; `LiveTradingCoordinator` nghe event đó và **dispatch**
`ExecuteOrderCommand`. Không có đường tắt từ event handler xuống `ITradingClient` (ADR §7).

### 2.2 Hạn mức là **domain policy**, không phải `if` trong coordinator

```
src/domain/trading/policies/trading_limit_policy.py
```

Bốn hạn mức, mỗi cái có lý do riêng, tất cả **bật mặc định**:

| Hạn mức | Vì sao |
| :--- | :--- |
| Số lệnh tối đa / phiên | Chặn vòng lặp tín hiệu lỗi — cái duy nhất chặn được lớp lỗi *"bug sinh ra lệnh"* |
| Notional tối đa / lệnh | Chặn lỗi làm tròn/nhập liệu sinh ra lệnh lớn bất thường |
| Đúng 1 vị thế mở / symbol | Giả định One-way mode (ADR §6); vi phạm nghĩa là state của app đã lệch sàn |
| Khoảng cách tối thiểu giữa 2 lệnh cùng symbol | Chặn tín hiệu dao động quanh biên bắn liên tục — cùng lớp vấn đề `BUG-077` (`_MIN_ZONE_BARS`) |

Là policy thuần vì nó phải test được không cần mạng, và vì nó là **quyết định nghiệp vụ**, không
phải chi tiết điều phối.

### 2.3 Ba rào an toàn trước khi một byte rời máy

1. `TradingVenue == FUTURES_TESTNET` (không có `MAINNET` để mà chọn — ADR §3).
2. Công tắc `trading.enabled`, **mặc định `false`**, user phải bật tường minh mỗi phiên (không
   nhớ qua lần khởi động — đây là ngoại lệ có chủ đích với cơ chế `EPIC-010`).
3. `EPIC-021D`'s connection status phải `reachable` **và** One-way mode.

### 2.4 Reconciliation lúc bật, không tin state trong RAM

Trước lệnh đầu tiên của mỗi phiên: đọc `get_positions()` và `get_open_orders()`, nạp vào state.
Tài khoản testnet có thể đã bị đổi bởi web hoặc một phiên app khác (ADR §4). Nếu sàn có vị thế mà
app không biết → **từ chối bật**, hiển thị cho user quyết định, không tự đóng.

### 2.5 Log: `DEBUG`, không `INFO` — bài học `BUG-042`

`SignalLogHandler` gắn ở logger gốc `"App"` mức INFO, nên **mọi** dòng INFO đi qua queued signal
sang UI thread và chạy trọn một chu kỳ `beginInsertRows`/`endInsertRows`. `BUG-042`: 838 trade →
5.028 dòng trong 2 giây → UI đơ (bẫy 9, `ONBOARDING.md` §8). Đường xử lý tick/tín hiệu chạy mỗi
nến, mỗi symbol — dùng `logger.debug()`, và chỉ log `INFO` cho sự kiện một-lần-có-nghĩa
(lệnh gửi, lệnh khớp, hạn mức chạm trần).

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/application/use_cases/trading/execute_order/` | **Mới** — command + handler |
| `src/domain/trading/policies/trading_limit_policy.py` | **Mới** — 4 hạn mức |
| `src/domain/trading/policies/position_sizing_bridge.py` | **Mới** — dùng lại `PositionSizing` của backtest để tính khối lượng từ số dư thật |
| `src/application/services/live_trading_coordinator.py` | **Mới** — nghe `SignalGeneratedEvent`, áp policy, dispatch command |
| `market_tick_event_handler.py` | Thay `logger.info()` bằng `StrategyEngine.on_tick()`; **xoá** comment "later" |
| `src/config/app_config.json` + `config_keys.py` | `trading.enabled` (false), 4 key hạn mức |
| `src/binance_bot_module.py` | Đăng ký coordinator + handler; `OrderSubmissionMode.LIVE` mở tại đây |

## 4. Kiểm thử

- **Unit (policy, BVA):** từng hạn mức tại biên — đúng bằng trần, dưới 1, trên 1. Mutation-verify:
  đổi `>=` thành `>` → test phải đỏ.
- **Unit:** cả ba rào an toàn, mỗi cái chặn độc lập (tắt từng cái một, hai cái còn lại vẫn chặn).
- **Unit:** reconciliation thấy vị thế lạ → từ chối bật, **không** tự đóng vị thế.
- **Integration (fake server):** một `SignalGeneratedEvent` → đúng **một** lệnh gửi đi; hai tín
  hiệu liên tiếp trong khoảng chặn → lệnh thứ hai bị chặn, có lý do ghi nhận được.
- **Business acceptance (`testing-rule.md` §2):** tín hiệu SHORT phải sinh lệnh SELL kèm
  `positionSide` đúng, không phải một lệnh đóng LONG. Đây chính là hành vi mà việc chọn Futures
  thay vì Spot tồn tại để phục vụ (ADR §1) — không kiểm thì lựa chọn đó không có bằng chứng.
- **Testnet tier (opt-in):** một lệnh MARKET khối lượng tối thiểu, khớp thật, rồi đóng lại. Đây là
  lần đầu tiên trong epic có lệnh khớp.

## 5. Mốc chạy được

**Lệnh khớp thật đầu tiên — và nó chạy headless, chưa cần đụng tới UI.**

```bash
# Mặc định là DRY-RUN. Phải gõ --live mới có lệnh thật.
PYTHONPATH=. python Sagittarius_Elite_Warrior/src/main.py trade-once \
  --symbol BTCUSDT --interval 5m --strategy ema_trend_pullback
```

```text
Nến gần nhất : 2026-09-01 14:35 UTC  close=64,102.30
Chiến lược   : ema_trend_pullback → SIGNAL BUY (ema_fast cắt lên trong xu hướng tăng)
Hạn mức      : lệnh 1/20 phiên ✔   notional 128.20 ≤ 500 ✔   vị thế BTCUSDT: chưa có ✔
                khoảng cách lệnh trước: n/a ✔
Chế độ       : DRY-RUN → dừng ở đây. Thêm --live để đặt thật.
```

Với `--live`:

```text
Chế độ       : LIVE
Đã gửi       : SEW-a91f4c72e0b8   → NEW
Trạng thái   : FILLED  0.002 @ 64,105.10   phí 0.0026 USDT
```

`trade-once` chạy **đúng một vòng rồi thoát** — không phải một daemon. Đó là lựa chọn có chủ đích
cho mốc này: một vòng thì quan sát được trọn vẹn, và một bug trong vòng lặp không thể bắn hàng
trăm lệnh trong lúc anh còn đang đọc output.

Ca chạm hạn mức cũng phải nhìn thấy được, vì đó là thứ bảo vệ anh:

```text
Hạn mức      : ✘ CHẶN — đã có vị thế BTCUSDT đang mở (one_position_per_symbol)
Không gửi lệnh nào.
```
