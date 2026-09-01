# EPIC-021I — UI: banner môi trường, sổ lệnh/vị thế, Emergency Stop

- **Trạng thái:** 🔴 Chưa bắt đầu
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021H`

---

## 1. Bối cảnh & vấn đề thật

Sau `EPIC-021H`, app đặt được lệnh và biết chuyện gì xảy ra với chúng — nhưng người dùng thì
không thấy gì ngoài log. Ba thiếu sót có hậu quả thật:

1. **Không nhìn ra mình đang ở môi trường nào.** Đây là thứ tuyệt đối không được suy đoán từ trí
   nhớ. Một màn hình trông giống hệt nhau ở testnet và mainnet là tiền đề của sai lầm đắt nhất
   mà epic này có thể gây ra sau này.
2. **Không có chỗ nhìn lệnh và vị thế đang mở.** `EPIC-021G` từ chối bật khi phát hiện vị thế lạ
   — nhưng user cần **thấy** nó để quyết định.
3. **Không có cách dừng khẩn cấp.** `BOT-008` đã ghi yêu cầu này từ đầu (*"Cần có cơ chế ngắt
   khẩn cấp (Emergency Stop)"*) và nó chưa từng được làm.

Ngoài ra, cảnh báo lệch nguồn (ADR §2.2) sống ở đây: khi chart hiển thị giá mainnet còn lệnh
khớp trên testnet, người dùng phải được nói thẳng rằng **giá nhìn thấy không phải giá khớp**.

## 2. Thiết kế + lý do

### 2.1 Banner môi trường: `PageShell`, không phải widget mới của một màn

`EPIC-020` đã dựng `PageShell` (header / context-bar / workspace+rail / console) và áp cho cả 4
màn. Banner môi trường thuộc **header** của shell — đặt ở đó thì nó xuất hiện ở mọi màn theo
đúng nghĩa "trạng thái toàn hệ thống", và không màn nào có thể quên vẽ nó.

`VenueAlignment` (ADR §2.2) là type quyết định banner nói gì: `ALIGNED` (cùng venue) /
`DATA_MAINNET_ORDERS_TESTNET` (cảnh báo lệch giá) / `TRADING_DISABLED`. Ba trạng thái, ba màu, ba
câu — không phải một chuỗi ghép trong widget.

### 2.2 Sổ lệnh & vị thế: widget QML, ViewModel test được không cần GUI

`EPIC-015` đã chốt hình dạng này và đã đo: widget ở DIR riêng, ViewModel test riêng không cần
GUI. Dùng lại đúng khuôn `DatabaseStatusTable`/`KlineInspectorTable`, kể cả bài học `BUG-076`:
mọi cột chuỗi dài phải có `elide: Text.ElideRight` + `Layout.minimumWidth: 0`.

Dữ liệu đến từ `OrderFeed` (`EPIC-021H`) — không màn nào tự nghe bus.

### 2.3 Emergency Stop là một use case, không phải một slot

```
src/application/use_cases/trading/emergency_stop/{command.py,handler.py,__init__.py}
```

Ba việc, **theo đúng thứ tự này**, và thứ tự là một phần của thiết kế:

1. Tắt giao dịch (`trading.enabled = false`) — chặn lệnh mới **trước tiên**, nếu không thì vừa
   đóng vừa có lệnh mới vào.
2. Huỷ toàn bộ lệnh chờ (`cancel_all_orders`).
3. Đóng mọi vị thế mở bằng lệnh MARKET `reduceOnly`.

Mỗi bước báo kết quả riêng: đóng vị thế **có thể thất bại** (mất mạng, sàn từ chối), và một nút
báo "đã dừng" trong khi vị thế còn mở là lời nói dối nguy hiểm nhất trong toàn bộ epic. Kết quả
là một VO liệt kê từng bước thành/bại, không phải `bool`.

Nút này **không** đi qua `@safe_ui_action` nuốt lỗi im lặng — bẫy 8 (`ONBOARDING.md` §8): một slot
có thể chết giữa chừng và mọi dòng sau không chạy. Lỗi ở đây phải hiện lên UI.

### 2.4 Trade marker trên chart — nối vào cái đã chờ sẵn

`BOT-009` để dở Trade Markers Manager vì *"chưa có `OrderFilledEvent` thật"*. `EPIC-021H` sinh ra
đúng event đó. Nối vào, dùng lại lớp marker của backtest chart, và tôn trọng bài học `BUG-077`:
marker dày đặc phải có ngưỡng/LOD, không vẽ mỗi sự kiện một item.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/domain/value_objects/venue_alignment.py` | **Mới** — 3 trạng thái |
| `.../ui/components/environment_banner/` | **Mới** — widget banner + ViewModel |
| `.../ui/components/order_book_panel/` | **Mới** — bảng lệnh + vị thế (QML + ViewModel) |
| `src/application/use_cases/trading/emergency_stop/` | **Mới** — command + handler + VO kết quả |
| `.../ui/screens/*/`(4 màn) | Banner qua `PageShell` header — không sửa từng màn |
| `.../screens/backtest/logic/` (chart) | Nối `OrderFilledEvent` vào trade marker |
| `settings_view.py` | Công tắc bật/tắt giao dịch + nút Emergency Stop |

## 4. Kiểm thử

- **Unit (ViewModel):** 3 trạng thái `VenueAlignment` → 3 nội dung banner; không test màu sắc cứng
  (bẫy 3, `ONBOARDING.md` §8 — đừng assert hằng số dễ trôi).
- **Unit:** Emergency Stop chạy đúng thứ tự 3 bước; bước 3 thất bại → kết quả báo **thất bại một
  phần**, không báo thành công. Mutation-verify: đảo thứ tự bước 1 và 2 → test phải đỏ.
- **Integration:** bấm Emergency Stop khi có 2 lệnh chờ + 1 vị thế (fake server) → đủ 3 lời gọi,
  đúng thứ tự, và giao dịch tắt.
- **Integration:** `OrderFilledEvent` → marker xuất hiện đúng vị trí thời gian/giá trên chart.
- **Sanity:** app boot với giao dịch tắt → banner ở trạng thái `TRADING_DISABLED`, không cảnh báo
  Qt nào (`diagnostic_guard`).
- **Async UI (`async-ui-action-rule.md`):** Emergency Stop chạy nền, không khoá UI, và **không**
  bị `@safe_ui_action` nuốt lỗi.
