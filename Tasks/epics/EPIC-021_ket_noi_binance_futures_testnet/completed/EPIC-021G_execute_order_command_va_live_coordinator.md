# EPIC-021G — `ExecuteOrderCommand` + `LiveTradingCoordinator`: lệnh thật đầu tiên

- **Trạng thái:** ✅ Hoàn thành (2026-09-02)
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

## 6. Ghi chú triển khai

### 6.1 Phát hiện an toàn nghiêm trọng nhất phiên này: §2.1 tự mâu thuẫn nếu làm đúng nghĩa đen

§2.1 viết "`LiveTradingCoordinator` nghe event đó [`SignalGeneratedEvent`] và dispatch
`ExecuteOrderCommand`" — đọc thẳng nghĩa là subscribe `app.event_bus.on(SignalGeneratedEvent,
coordinator.handle)`. Đọc `RunHistoricalTickBacktestCommandHandler` (dòng gọi `build_engine`) thì
thấy backtest **dùng chung đúng một `IEventPublisher` singleton toàn app** để phát
`SignalGeneratedEvent` — nghĩa là một `LiveTradingCoordinator` subscribe theo đúng nghĩa đen của
§2.1 sẽ nhận **cả tín hiệu từ một lượt backtest**, và chỉ bị chặn bởi 3 rào an toàn (vốn có thể
đều đang mở nếu user đã bật trading để test live trước đó) — tức là **chạy một backtest có thể vô
tình bắn lệnh thật**. Đây đúng loại lỗi §1 của task này nói phải chặn ("một vòng lặp tín hiệu bắn
hàng trăm lệnh"), chỉ khác nguồn: không phải bug logic mà là kiến trúc event-bus dùng chung.

Xử lý: `MarketTickEventHandler` gọi thẳng `LiveTradingCoordinator.handle(signal)` bằng giá trị
`Signal` mà `StrategyEngine.on_tick()` đã trả về cho nó — **không** qua `event_bus.on(...)`. Không
có code backtest nào chạm được đường này nữa. `ADR §7` ("không có đường tắt từ event handler xuống
`ITradingClient`") vẫn giữ nguyên: `MarketTickEventHandler` gọi `LiveTradingCoordinator`, và
coordinator đó vẫn đi qua `ExecuteOrderCommand` via `ICommandDispatcher`, không chạm
`ITradingClient` trực tiếp. Lý do đầy đủ đã ghi trong docstring của cả hai file
(`live_trading_coordinator.py`, `market_tick_event_handler.py`) để không ai "sửa lại cho đúng" §2.1
mà không đọc lại lý do này.

### 6.2 `ITradingClient.get_positions()`/`get_open_orders()` cần tham số symbol tuỳ chọn

§2.4 viết "đọc `get_positions()` và `get_open_orders()`" không kèm symbol — tức reconciliation
toàn tài khoản. Nhưng `EPIC-021E` định nghĩa hai method này với `symbol: str` **bắt buộc**. Đã sửa
port (`i_trading_client.py`) và `FuturesTradingClient` để `symbol` thành `str | None = None`
(Binance thật cũng hỗ trợ gọi không kèm symbol) — mở rộng tương thích ngược, không phải thu hẹp.

### 6.3 `EnableTradingCommandHandler` không được phép phụ thuộc trực tiếp vào `ITradingClient`

`ITradingClient` chỉ được đăng ký trong DI khi `TradingVenue != DISABLED` (`EPIC-021F`). Nếu
`EnableTradingCommandHandler` nhận `ITradingClient` qua constructor, nó sẽ **không dựng được** khi
venue DISABLED — đúng lúc nó cần dựng được để tự báo `TRADING_VENUE_DISABLED`. Đổi sang tự dựng một
`FuturesTradingClient(..., OrderSubmissionMode.VALIDATE_ONLY)` bên trong (giống hệt cách
`ExecuteOrderCommandHandler` đã làm) — `VALIDATE_ONLY` không ảnh hưởng gì tới hai lệnh gọi chỉ-đọc
này. Nhờ vậy `EnableTradingCommand` **không** cần thêm vào `_NOT_DISPATCHED` của sanity
`test_composition_root.py` — chỉ `SubmitOrderCommand` (`EPIC-021F`) còn trong danh sách đó.

### 6.4 Guard `OrderSubmissionMode.LIVE` đổi từ "cấm toàn phần" sang "chỉ 1 file được phép"

Đổi tên `test_order_submission_mode_live_is_not_used_yet.py` →
`test_order_submission_mode_live_is_restricted.py`, sửa từ "hits == []" sang "hits ==
[execute_order/handler.py]" — đúng như `EPIC-021F` đã dự liệu ("gỡ trong chính 021G"). Vẫn quét
bằng `ast.Attribute`, không phải text thô, vì lý do đã ghi ở `EPIC-021F` §6.4: docstring giải thích
luật cũng phải nhắc tên bị cấm.

### 6.5 `client_order_id` bắt buộc → `PreviewOrderQuery` cần thêm `reduce_only`

Bài kiểm thu nhận nghiệp vụ §4 ("tín hiệu SHORT phải sinh lệnh SELL kèm `positionSide` đúng,
không phải một lệnh đóng LONG") đòi hỏi phân biệt được SELL-để-đóng-LONG với SELL-để-mở-SHORT —
Binance One-way mode dùng chung side SELL cho cả hai, chỉ khác `reduceOnly`. `PreviewOrderQuery`
(`EPIC-021E`) không có field này (không cần cho order-preview/order-dry-run). Thêm
`reduce_only: bool = False` (mặc định giữ nguyên hành vi cũ, `order-preview`/`order-dry-run` không
đổi), thread qua `PreviewOrderQueryHandler` vào `Order.reduce_only`. Mapping SignalAction → (side,
reduce_only) sống ở `domain/trading/policies/signal_action_to_order_intent.py`, khoá bằng test
`test_sell_and_short_share_the_same_side_but_differ_on_reduce_only`.

### 6.6 Bốn hạn mức thành 4 config số, kể cả "một vị thế/symbol"

Task viết "Đúng 1 vị thế mở/symbol" như một luật cố định, nhưng "4 key hạn mức" ở §3 ngụ ý cả bốn
đều là số cấu hình được. Đặt `TRADING_MAX_POSITIONS_PER_SYMBOL` (mặc định 1) thay vì hard-code
`== 0`, để chỗ cho tương lai (không có ý định nới lỏng One-way trong epic này — ADR §6 vẫn giữ).

### 6.7 `MarketTickEventHandler`/`LiveTradingCoordinator` chỉ 1 symbol — quyết định phạm vi, không phải thiếu sót

Mỗi `StrategyEngine` giữ state chỉ báo tăng dần theo từng nến (`BOT-042B/C`). Trộn nến hai symbol
qua cùng một `StrategyEngine` sẽ làm hỏng state đó. Task không có UI chọn nhiều symbol/chiến lược
live (đó là `EPIC-021I`), nên `TRADING_LIVE_SYMBOL`/`TRADING_LIVE_STRATEGY_KEY` (mặc định rỗng —
"chưa cấu hình live") là phạm vi thật của task này: một symbol, một chiến lược, cấu hình tĩnh.
Position sizing (`PERCENT_OF_EQUITY 20%`, leverage 1x) cũng hard-code với lý do tương tự — control
UI thật thuộc `EPIC-021I`.

### 6.8 Milestone `--live` không có dòng "Trạng thái: FILLED..." như ví dụ gốc

Ví dụ §5 cho `--live` in cả "Trạng thái: FILLED 0.002 @ 64,105.10 phí 0.0026 USDT" — dữ liệu khớp
lệnh **không có** trong response đồng bộ của `place_order()` (quyết định đã ghi từ `EPIC-021F` §6:
vòng đời thật là việc của `EPIC-021H`'s User Data Stream). Output thật của `trade-once --live` in
`client_order_id` + status ngay-sau-gửi (luôn `NEW`), kèm một dòng nói rõ trạng thái khớp thật sẽ
tới từ `EPIC-021H`, thay vì bịa số liệu chưa có thật.

### 6.9 Chiến lược trong ví dụ milestone dùng sai tên key thật

§5 viết `--strategy ema_trend_pullback`; key thật đã đăng ký trong `binance_bot_module.py` là
`ema_trend_confirm_pullback`. Danh sách `choices` của CLI dùng tên thật.

### 6.10 Kết quả kiểm thử cuối

- Ruff (`src tests scripts tools`): sạch — 3 lỗi baseline có sẵn ở `scripts/shutdown_*_probe.py`
  (không đụng tới); `ruff format --check` sạch.
- Mypy (`src`+`scripts`, một lệnh, từ thư mục superproject): `Success: no issues found in 226
  source files`. Một lỗi thật tự bắt được và sửa: `LiveTradingCoordinator` (dưới
  `application/services/`, có nằm trong phạm vi mypy — không như phần lớn coordinator khác dưới
  `presentation/`, bị loại trừ nguyên khối) cần `cast()` tường minh cho
  `ICommandDispatcher.dispatch()`'s kiểu trả về `object`.
- Sanity: 24/24 — xác nhận cả `ExecuteOrderCommand` lẫn `EnableTradingCommand` tự dựng được dù
  `TradingVenue` mặc định DISABLED (xem §6.3), không cần thêm vào `_NOT_DISPATCHED`.
- Unit (`-n 4`): 3160 passed, 1 failed —
  `test_pan_preview_moves_only_the_data_region_not_the_axes`. Đã root-cause và mở hồ sơ riêng ở
  [`BUG-083`](../../../bug_report/completed/BUG-083_pan_preview_test_drags_past_its_own_reanchor_boundary.md)
  (lỗi test, không phải lỗi sản phẩm; đỏ từ PR #140, 2026-08-27). Trước đó dòng này chỉ ghi "không
  liên quan" — 10/13 file task của epic đều ghi vậy, và đó chính là cách một cổng bắt buộc mất tác
  dụng.
- Guard: `test_order_submission_mode_live_is_restricted.py` xanh (đúng 1 file được phép);
  `test_only_the_session_factory_constructs_binance_client.py` (`EPIC-021A`) vẫn xanh;
  `grep -rln "class.*(ITradingClient)" src/` cho đúng 1 implementer.
- BVA đầy đủ cho cả 4 hạn mức (đúng bằng trần / dưới 1 / trên 1) + mutation-verify cho
  `MAX_ORDERS_PER_SESSION` (`test_mutation_verify_ge_not_gt`); 3 rào an toàn kiểm độc lập
  (`test_each_gate_blocks_independently_of_the_other_two`); reconciliation thấy vị thế lạ → từ
  chối bật, không tự đóng (`test_refuses_and_does_not_enable_when_unexpected_position_exists`).
- Chạy thật `main.py trade-once --symbol BTCUSDT --interval 5m --strategy
  ema_trend_confirm_pullback` trong sandbox (không có dữ liệu nến local) → thoát êm với thông báo
  "chạy `sync` trước", không traceback; `--strategy` sai tên → argparse tự chặn với danh sách hợp
  lệ, không traceback.

### 6.11 Hai bài kiểm thử §4 còn thiếu — bổ sung 2026-09-02

§4 liệt kê 5 nhóm test; §6.10 chỉ chứng minh được 3 nhóm đầu. Hai nhóm sau **chưa từng được viết**
(tier testnet là opt-in, nằm ngoài phạm vi này):

- **Integration (fake server):** *"một `SignalGeneratedEvent` → đúng **một** lệnh gửi đi; hai tín
  hiệu liên tiếp trong khoảng chặn → lệnh thứ hai bị chặn, có lý do ghi nhận được"*.
- **Business acceptance:** *"tín hiệu SHORT phải sinh lệnh SELL kèm `positionSide` đúng, không
  phải một lệnh đóng LONG"*.

`test_live_trading_coordinator.py` (unit, có sẵn) **không** phủ được hai cái này: nó dừng ở
`dispatcher.dispatch` và chỉ chứng minh coordinator *yêu cầu* đúng command. Mọi tầng còn có thể
đảo ngược hướng lệnh đều nằm sau lời gọi đó — `PreviewOrderQueryHandler` làm tròn,
`map_order_to_futures_params`, và phần form-encode của `python-binance`. §4 nói về **request mà
Binance nhận được**, nên assertion phải đọc request Binance nhận được.

Bổ sung: `tests/integration/application/test_live_trading_pipeline_against_fake_server.py` — 4
test, chạy trọn chuỗi sizing → làm tròn → map params → HTTP thật → sổ lệnh của fixture, rồi đọc
lại `GET /fapi/v1/openOrders` bằng `urllib` **thẳng**, không qua adapter của app (hỏi chính code
đang bị kiểm để biết nó gửi gì là lập luận vòng tròn).

| Đột biến gieo vào code thật | Test chết |
| :--- | :--- |
| `SignalAction.SHORT` → `reduce_only=True` | `..._short_signal_opens_a_short_...` |
| `_ONE_WAY_POSITION_SIDE = "BOTH"` → `"LONG"` | 2 test acceptance (SHORT + SELL) |
| Vô hiệu hoá cả `MAX_POSITIONS_PER_SYMBOL` lẫn `MIN_ORDER_INTERVAL` | `..._second_signal_inside_the_window_...` (lệnh thứ 2 ra tới sàn thật) |
| `quantity = 0` trong coordinator (không gửi gì) | cả 4 |

Ba ghi chú về sự thật quan sát được, ghi lại vì đều dễ bị viết trại thành thứ khác:

1. **Lý do chặn lệnh thứ hai không phải cái §4 ngụ ý.** Cả `MAX_POSITIONS_PER_SYMBOL` lẫn
   `MIN_ORDER_INTERVAL` đều fail, và handler báo cái **đầu tiên** trong bốn —
   `MAX_POSITIONS_PER_SYMBOL`. Không phải lỗi: `record_order_sent()` đánh dấu symbol là "coi như
   đang mở" ngay khi gửi, trước mọi xác nhận khớp (docstring của chính nó). Test assert **cả hai**
   check đều fail, nên đổi một trong hai limit sau này không thể âm thầm để lệnh thứ hai lọt.
2. **`ITradingAccountReader` bị stub, không chạy qua fixture.** Tài khoản giả cố định 15.000 USDT;
   sizing 20%/1x của task này sẽ cho notional ~2.944 USDT, vượt hạn mức 500 → *mọi* test ở đây sẽ
   dừng ở limit trước khi chạm hành vi cần kiểm. Reader thật đã có round-trip riêng ở
   `test_futures_account_reader_against_fake_server.py`.
3. **Giới hạn của fixture, đã đo chứ không suy đoán.** Sổ lệnh của fixture khoá theo
   `newClientOrderId`, nên gửi **cùng một** `Order` hai lần bị gộp thành một và test đếm vẫn xanh.
   Hình thái đó không xảy ra qua pipeline này (`generate_client_order_id()` sinh id mới mỗi lượt)
   và Binance thật từ chối id trùng. Dạy fixture cách từ chối đó đòi **đoán một mã lỗi repo chưa
   verify từ source**, nên ghi lại giới hạn thay vì che nó đi. Hai lệnh **khác nhau** ra tới sàn
   thì vẫn bắt được.

**Cổng bắt buộc sau khi bổ sung:** `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` —
Ruff lint ✅ · Ruff format (940 file) ✅ · Mypy (231 file) ✅ · Skill refs ✅ · Sanity ✅ ·
`1 failed, 3316 passed, 4 skipped` (3312 → 3316, đúng 4 test mới; 1 đỏ duy nhất là `BUG-083`) ·
quét log bắt buộc **sạch** ("no WARNING/ERROR/CRITICAL log records",
`logs/ci-local-20260902-084228.log`).
