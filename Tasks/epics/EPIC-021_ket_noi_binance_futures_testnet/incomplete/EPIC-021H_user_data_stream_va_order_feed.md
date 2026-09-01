# EPIC-021H — User Data Stream: sự thật về lệnh đến từ sàn + `OrderFeed`

- **Trạng thái:** 🔴 Chưa bắt đầu
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
