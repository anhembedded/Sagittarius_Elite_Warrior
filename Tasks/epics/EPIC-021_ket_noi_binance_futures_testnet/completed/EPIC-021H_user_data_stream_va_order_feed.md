# EPIC-021H — User Data Stream: sự thật về lệnh đến từ sàn + `OrderFeed`

- **Trạng thái:** ✅ Hoàn thành (2026-09-02)
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021G` · **Chặn:** `EPIC-021I`

---

## 1. Bối cảnh & vấn đề thật

Sau `EPIC-021G`, app biết mình **đã gửi** gì. Nó vẫn không biết chuyện gì thật sự xảy ra: response
của `futures_create_order` chỉ nói *"sàn đã nhận"*. Một lệnh MARKET có thể khớp nhiều mức giá,
khớp một phần, bị huỷ vì thiếu margin sau đó, hoặc vị thế bị đổi bởi tác nhân khác (ADR §4).

Binance có kênh riêng cho việc này: **User Data Stream** — `futures_user_socket`, mang
`ORDER_TRADE_UPDATE` và `ACCOUNT_UPDATE`, xác thực bằng `listenKey` từ
`futures_stream_get_listen_key` và phải `futures_stream_keepalive` định kỳ (listenKey hết hạn
sau ~60 phút nếu không gia hạn).

## 2. Thiết kế + lý do

### 2.1 Một service riêng, không nhét vào `BinanceWebsocketService`

```
src/infrastructure/binance/futures_user_data_stream.py
```

`BinanceWebsocketService` phục vụ **kline công khai**, không cần key, và một lỗi ở đó chỉ làm
chart đứng. User Data Stream cần key, cần keepalive, và mất nó nghĩa là app **mù về tiền của
mình**. Khác vòng đời, khác hậu quả khi hỏng → khác file (`architecture-rule.md` §5.5: đổi cái
này không bắt buộc sửa cái kia).

Tái dùng đúng khuôn đã có của service kline: `ITaskManager.spawn` + `CancellationToken`, thoát
hợp tác, đóng client trong `finally`. Đừng viết vòng đời task mới.

### 2.2 `listenKey` keepalive là một cơ chế có tên, không phải một `while True` ẩn

Gia hạn định kỳ, và **tái tạo** listenKey khi mất kết nối — một reconnect dùng lại listenKey đã
hết hạn sẽ nối được nhưng không nhận được gì, dạng hỏng im lặng tệ nhất. Phải có log `INFO` khi
tái tạo (sự kiện một-lần-có-nghĩa, đúng `logging-rule.md`).

### 2.3 `OrderFeed` — bus + đúng một Feed (`architecture-rule.md` §6)

Trạng thái lệnh/vị thế là **sự thật của hệ thống**: bảng lệnh quan tâm, chart marker quan tâm,
log quan tâm, và một màn hình tương lai cũng sẽ quan tâm. Theo §6.2, câu hỏi *"màn khác muốn biết
chuyện này có vô lý không?"* trả lời **không vô lý** → lên bus, **đúng một** subscriber chuẩn hoá.

```
src/presentation/ui/common/order_feed.py     # kế thừa BaseFeed, cạnh 3 Feed sẵn có
```

Đây chính là "chỗ hạ cánh có tên" mà `BaseFeed` được dựng ra để phục vụ (`EPIC-008`,
`architecture-rule.md` §7.1). Không tạo hình dạng thứ tư.

### 2.4 Sàn là nguồn sự thật; state trong RAM là cache

Khi `ORDER_TRADE_UPDATE` mâu thuẫn với state nội bộ (app tưởng `NEW`, sàn nói `FILLED` từ lâu),
**sàn thắng**, và chênh lệch được log `WARNING`. Không im lặng ghi đè: một chênh lệch lặp lại là
triệu chứng của một bug thật ở `EPIC-021G`.

### 2.5 Cross-thread: dùng `QtEventBridge`, không tự bắc cầu

Stream chạy trên task nền. Đưa dữ liệu về main thread bằng cơ chế sẵn có (`EPIC-008`), và **đừng
xoá** Qt queued signal nào đang bắc cầu thread — `Handover.md` §3 và `architecture-rule.md` §6.1
đã ghi rõ đó là code **đúng**, 47/48 signal tồn tại vì lý do đó.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/application/ports/i_user_data_stream.py` | **Mới** — port |
| `src/infrastructure/binance/futures_user_data_stream.py` | **Mới** — implement + keepalive listenKey |
| `src/infrastructure/binance/user_data_event_parser.py` | **Mới** — payload sàn → domain event |
| `src/presentation/ui/common/order_feed.py` | **Mới** — Feed thứ 4 |
| `src/application/services/live_trading_coordinator.py` | State lệnh/vị thế cập nhật từ stream, không từ response |
| `src/binance_bot_module.py` | Đăng ký stream, khởi động khi bật giao dịch |

## 4. Kiểm thử

- **Unit (parser):** payload `ORDER_TRADE_UPDATE` thật (fixture tĩnh) cho từng trạng thái, gồm
  **khớp một phần** và **khớp nhiều mức giá** — hai ca mà backtest chưa bao giờ có.
- **Unit:** listenKey hết hạn → tái tạo; reconnect **không** dùng lại key cũ (mutation-verify: bỏ
  bước tái tạo → test đỏ).
- **Unit:** stream mâu thuẫn state nội bộ → sàn thắng + log `WARNING`.
- **Integration:** `OrderFilledEvent` đi qua `OrderFeed` tới đúng nơi hiển thị; đúng **một**
  subscriber chuẩn hoá (guard `EPIC-008` sẵn có phải vẫn xanh).
- **Sanity:** app boot với giao dịch **tắt** không mở stream nào, không phát cảnh báo nào
  (`diagnostic_guard` — im lặng là assertion).
- **Testnet tier (opt-in):** đặt một lệnh thật → nhận `ORDER_TRADE_UPDATE` trong thời gian giới
  hạn, và trạng thái cuối là `FILLED`. Chờ bằng điều kiện có tên, **không** bằng `sleep`
  (`testing-rule.md` §2).

## 5. Mốc chạy được

Mốc này quan sát được rõ nhất bằng **hai terminal**:

```bash
# Terminal 1 — nghe sàn nói
PYTHONPATH=. python Sagittarius_Elite_Warrior/scripts/epic021h_user_stream_probe.py --seconds 120
```

```bash
# Terminal 2 — làm một việc gì đó
PYTHONPATH=. python Sagittarius_Elite_Warrior/src/main.py trade-once --symbol BTCUSDT --live ...
```

Terminal 1 in ra vòng đời thật, do **sàn** kể lại chứ không phải app tự kể:

```text
14:35:02  ORDER_TRADE_UPDATE  SEW-a91f4c72e0b8  NEW              qty 0.002  filled 0.000
14:35:02  ORDER_TRADE_UPDATE  SEW-a91f4c72e0b8  PARTIALLY_FILLED qty 0.002  filled 0.001 @ 64,105.10
14:35:02  ORDER_TRADE_UPDATE  SEW-a91f4c72e0b8  FILLED           qty 0.002  filled 0.002 @ 64,105.35
14:35:02  ACCOUNT_UPDATE      BTCUSDT  pos 0.002  entry 64,105.35  uPnL -0.02
14:52:31  listenKey keepalive OK (còn hạn 59 phút)
```

Dòng `PARTIALLY_FILLED` là thứ **backtest chưa bao giờ có** — trong mô phỏng mọi lệnh khớp trọn
vẹn tức thì. Nhìn thấy nó chảy qua chính là bằng chứng rằng nguồn sự thật đã đúng (ADR §4).

Mốc phụ, quan trọng không kém: mở app với giao dịch **tắt** → probe không nhận gì, và
`tests/sanity` vẫn im lặng tuyệt đối. Một stream tự mở khi chưa ai bật là bug.

## 6. Ghi chú triển khai

### 6.1 `listenKey` keepalive: ủy quyền cho `python-binance`, không viết lại

§2.2 yêu cầu gia hạn định kỳ + tái tạo khi mất kết nối, có log `INFO` khi tái tạo.
Đọc thẳng mã nguồn `python-binance`'s `BinanceSocketManager.futures_user_socket()` →
`KeepAliveWebsocket` (`binance/ws/keepalive_websocket.py`) cho thấy nó đã tự làm đúng
việc này: `_keepalive_socket()` gọi lại `futures_stream_get_listen_key()` theo chu kỳ —
đây là API "create-or-extend" của chính Binance, trả về cùng key nếu còn hạn, key mới
nếu đã hết — và tự reconnect bằng key mới khi key đổi. `FuturesUserDataStream` dùng thẳng
entry point công khai `bsm.futures_user_socket()` thay vì tự viết một bộ định thời
riêng cạnh các hàm `AsyncClient` private (`_get_futures_socket`, `futures_stream_keepalive`)
— viết lại logic thư viện đã làm đúng chỉ tạo ra một bản triển khai thứ hai không ai
review. Đây là một thu hẹp phạm vi có chủ đích so với câu chữ của §2.2, không phải một
thiếu sót.

### 6.2 `FuturesUserDataStream` không phụ thuộc `ITradingClient` trực tiếp

Cùng lý do đã áp dụng cho `EnableTradingCommandHandler`/`ExecuteOrderCommandHandler`
(`EPIC-021G`): `ITradingClient` chỉ được đăng ký khi `TradingVenue != DISABLED`
(`binance_bot_module.py`). Nếu constructor nhận thẳng `ITradingClient`, class này —
và do đó `EnableTradingCommandHandler` một khi phụ thuộc `IUserDataStream` — sẽ chỉ
constructible khi trading đã bật, phá lại đúng bất biến DI đã sửa ở G. Thay vào đó,
`FuturesUserDataStream` nhận `session_factory`/`credentials_provider`/`metadata_provider`
thô và tự dựng `FuturesTradingClient(..., VALIDATE_ONLY)` bên trong `_run_stream()`,
sau khi đã resolve credentials ở đó (trả về êm nếu không có key, không throw).

### 6.3 `IUserDataStream` đăng ký vô điều kiện

Không giống `ITradingClient`, `IUserDataStream` đăng ký singleton trong DI **không
điều kiện** — cùng nhóm rủi ro với `ITradingAccountReader` (chỉ đọc). Không có gì tự
gọi `.start()` ngoài nhánh bật-thành-công của `EnableTradingCommandHandler`, nên "app
boot với giao dịch tắt → không stream nào mở" đúng theo cấu trúc, không cần thêm guard.

### 6.4 `account_update_changed_symbols()` cố ý bao gồm symbol vừa về flat

Một vị thế vừa đóng (`positionAmt=0`) tự nó là một thay đổi thật, không phải noise cần
lọc bỏ. `_handle_account_update` không cố dựng `LivePosition` từ payload `ACCOUNT_UPDATE`
(thiếu `markPrice`/`leverage`/`liquidationPrice`) — luôn fetch lại qua
`ITradingClient.get_positions(symbol)` (REST), khớp đúng nguyên tắc "sàn là nguồn sự
thật" ở độ chi tiết cao hơn payload stream cung cấp.

### 6.5 §3 nói đổi `live_trading_coordinator.py` — thực tế không cần

Bảng file ở §3 liệt `live_trading_coordinator.py` là nơi "state lệnh/vị thế cập nhật từ
stream, không từ response". Đọc lại `TradingSessionState` (đã viết từ G) thì
`known_open_symbols` không do `LiveTradingCoordinator` sở hữu — nó được set lạc quan bởi
`record_order_sent()` (gọi từ `ExecuteOrderCommandHandler`) và **sửa lại theo sự thật của
sàn** bởi hàm mới `position_state_reconciler.reconcile_position_state()`, gọi từ
`FuturesUserDataStream._handle_account_update()` mỗi khi có `ACCOUNT_UPDATE`. Đúng yêu
cầu của §3, chỉ khác nơi đặt — không có gì trong `live_trading_coordinator.py` cần sửa,
nên file đó không nằm trong diff của task này.

### 6.6 Mốc chạy được: thêm `scripts/epic021h_user_stream_probe.py`

§3 không liệt kê file này, nhưng §5 mô tả nó là cách quan sát mốc (hai terminal). Không
gọi qua `ITaskManager.spawn()` (cần `App` context đầy đủ: async runtime, recorder,
container) — thay vào đó `await` thẳng `FuturesUserDataStream._run_stream()`, bọc trong
`asyncio.wait_for(..., timeout=seconds)`, đúng coroutine mà `.start()` lẽ ra sẽ giao cho
task manager. Đã smoke-test tại chỗ (không cấu hình credentials) — thoát êm với log lỗi
`"No exchange credentials configured"`, không crash. Không thể chạy full milestone
(nhận `ORDER_TRADE_UPDATE`/`ACCOUNT_UPDATE` thật) trong sandbox này vì mọi egress tới
`*.binance.*` bị chặn theo chính sách — cần máy có mạng thật + credentials testnet.

Cũng phát hiện: hiện chưa có CLI command nào gọi `EnableTradingCommand` (`main.py
trade-once` gọi thẳng `ExecuteOrderCommand`, bỏ qua bước bật trading) — nghĩa là mốc §5
đúng nghĩa đen (bật trading rồi mới trade-once) cần `EPIC-021I`'s Trading screen hoặc một
CLI command "enable-trading" chưa tồn tại. Không phải phạm vi của task này; ghi lại để
`EPIC-021I` không bất ngờ.

### 6.7 Kết quả kiểm thử

- Unit mới: parser 12/12, reconciler 3/3, stream routing 7/7, `OrderFeed` 3/3,
  `enable_trading` (cập nhật) 5/5 — 30/30.
- Ruff (`src tests scripts tools`): 0 lỗi ngoài 3 lỗi baseline đã biết ở
  `scripts/shutdown_database_sync_probe.py`/`scripts/shutdown_sync_probe.py` (không đụng).
- `ruff format --check`: sạch.
- Mypy (chạy từ `/home/user`, `--namespace-packages --explicit-package-bases`): 0 lỗi,
  231 file nguồn (gồm `scripts/epic021h_user_stream_probe.py`).
- `tests/sanity`: 24/24.
- `tests/unit` đầy đủ (`-n 4`, offscreen): 3190 passed, 1 failed — thất bại duy nhất là
  `test_pan_preview_moves_only_the_data_region_not_the_axes` (chart pan pixel-rendering),
  đã xác nhận không liên quan qua các task E/F/G trước đó.
