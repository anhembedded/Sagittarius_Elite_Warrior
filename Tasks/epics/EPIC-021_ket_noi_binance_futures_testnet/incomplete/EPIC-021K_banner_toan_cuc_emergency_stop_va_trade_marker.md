# EPIC-021K — Banner môi trường toàn cục, Emergency Stop, trade marker trên chart

- **Trạng thái:** 🔴 Chưa bắt đầu
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021I`

---

## 1. Bối cảnh & vấn đề thật

`EPIC-021I` cho màn Giao dịch một chỗ đứng riêng. Còn lại ba việc **xuyên suốt cả 5 màn**, không
thuộc về màn nào — nên chúng đứng riêng ở đây thay vì phình `021I` ra:

1. **Không nhìn ra mình đang ở môi trường nào.** Đây là thứ tuyệt đối không được suy đoán từ trí
   nhớ. Một giao diện trông giống hệt nhau ở testnet và mainnet là tiền đề của sai lầm đắt nhất
   mà epic này có thể gây ra về sau. Và ngay hôm nay đã có một cái bẫy thật: chart hiển thị giá
   **mainnet** trong khi lệnh khớp trên **testnet** (ADR §2.2) — người dùng phải được nói thẳng.
2. **Không có cách dừng khẩn cấp.** `BOT-008` ghi yêu cầu này từ đầu (*"Cần có cơ chế ngắt khẩn
   cấp (Emergency Stop)"*) và nó chưa từng được làm.
3. **Chart không hiện lệnh thật.** `BOT-009` để dở Trade Markers Manager với lý do ghi rõ: *"chưa
   có `OrderFilledEvent` thật"*. `EPIC-021H` vừa sinh ra đúng event đó.

## 2. Thiết kế + lý do

### 2.1 Banner ở header của `PageShell` — một chỗ, năm màn

`EPIC-020` đã áp `PageShell` (header / context-bar / workspace+rail / console) cho cả 4 màn cũ, và
`EPIC-021I` dùng nó cho màn thứ 5. Đặt banner vào **header của shell** nghĩa là nó xuất hiện ở mọi
màn theo đúng nghĩa "trạng thái toàn hệ thống", và **không màn nào có thể quên vẽ nó** — khác hẳn
với việc mỗi màn tự thêm một widget.

`VenueAlignment` là type quyết định banner nói gì, không phải một chuỗi ghép trong widget:

| Trạng thái | Banner |
| :--- | :--- |
| `TRADING_DISABLED` | xám — *"Giao dịch đang TẮT. Chỉ xem dữ liệu."* |
| `ALIGNED` | vàng — *"FUTURES TESTNET — tiền giả lập."* |
| `DATA_MAINNET_ORDERS_TESTNET` | cam — *"Chart đang hiển thị giá MAINNET, lệnh khớp trên TESTNET. Giá thấy ≠ giá khớp."* |

Trạng thái thứ ba là lý do type này tồn tại: nó là hệ quả trực tiếp của việc anh chọn cấu hình
từng phần trong Settings, và nó **không** được phép chỉ nằm trong ADR (`architecture-rule.md` §7).

### 2.2 Emergency Stop là một use case, và **thứ tự là một phần của thiết kế**

```
src/application/use_cases/trading/emergency_stop/{command.py,handler.py,__init__.py}
```

Ba bước, đúng thứ tự này:

1. **Tắt giao dịch** (`trading.enabled = false`) — chặn lệnh mới **trước tiên**; đảo thứ tự nghĩa
   là vừa đóng vừa có lệnh mới vào.
2. **Huỷ toàn bộ lệnh chờ** (`cancel_all_orders`).
3. **Đóng mọi vị thế** bằng MARKET `reduceOnly`.

Kết quả là một VO liệt kê **từng bước thành/bại**, không phải `bool`. Lý do cứng: bước 3 **có thể
thất bại** (mất mạng, sàn từ chối, margin) — và một nút báo "đã dừng" trong khi vị thế còn mở là
lời nói dối nguy hiểm nhất trong toàn bộ epic.

Nút này **không** đi qua `@safe_ui_action`: bẫy 8 (`ONBOARDING.md` §8) — decorator đó nuốt exception
nên slot có thể chết giữa chừng và mọi dòng sau không chạy. Ở đây lỗi phải nổi lên UI.

### 2.3 Trade marker — nối vào cái đã chờ sẵn, tôn trọng bài học `BUG-077`

Dùng lại lớp marker của backtest chart. Marker dày đặc phải có ngưỡng/LOD — `BUG-077` vừa cho thấy
hàng chục item nhỏ sát nhau đọc thành một khối đen đặc, và cách sửa đúng là bỏ hẳn item dưới
ngưỡng chứ không vẽ tiếp rồi hy vọng.

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `src/domain/value_objects/venue_alignment.py` | **Mới** — 3 trạng thái |
| `.../ui/components/environment_banner/` | **Mới** — widget + ViewModel |
| `.../ui/kit/page_shell.py` (hoặc tương đương `EPIC-020`) | Cắm banner vào header — **một** chỗ sửa cho cả 5 màn |
| `src/application/use_cases/trading/emergency_stop/` | **Mới** — command + handler + VO kết quả từng bước |
| `.../ui/screens/trading/trading_view.py` | Nút Emergency Stop ở context bar |
| `.../screens/backtest/logic/` + chart Dev Board | Nối `OrderFilledEvent` vào trade marker |

## 4. Kiểm thử

- **Unit (ViewModel):** 3 `VenueAlignment` → 3 nội dung banner. Không assert mã màu cứng (bẫy 3,
  `ONBOARDING.md` §8 — assert thứ có ý nghĩa, không assert hằng số dễ trôi).
- **Unit:** Emergency Stop chạy đúng thứ tự 3 bước. **Mutation-verify:** đảo bước 1 và 2 → test
  phải đỏ. Nếu vẫn xanh thì test chưa chứng minh gì về thứ tự.
- **Unit:** bước 3 thất bại → kết quả báo **thất bại một phần**, không báo thành công.
- **Integration:** bấm Emergency Stop khi có 2 lệnh chờ + 1 vị thế (fake server) → đủ 3 lời gọi,
  đúng thứ tự, giao dịch tắt.
- **Integration:** banner hiện đúng ở **cả 5** màn — quét registry, không liệt kê tay từng màn.
- **Integration:** `OrderFilledEvent` → marker đúng vị trí thời gian/giá trên chart.

## 5. Mốc chạy được

**Mốc 1 — banner:** mở app, đi qua cả 5 màn, banner luôn ở đó và đổi nội dung theo cấu hình:

```text
Settings: nguồn dữ liệu = MAINNET_PUBLIC, nơi đặt lệnh = FUTURES_TESTNET
→ mọi màn:  ⚠ Chart hiển thị giá MAINNET — lệnh khớp trên TESTNET. Giá thấy ≠ giá khớp.

Đổi nguồn dữ liệu = FUTURES_TESTNET
→ mọi màn:  ⓘ FUTURES TESTNET — tiền giả lập.
```

**Mốc 2 — Emergency Stop, chạy thật:** đặt trước 1 vị thế + 1 lệnh chờ bằng `trade-once --live`,
rồi bấm nút:

```text
DỪNG KHẨN CẤP
  1. Tắt giao dịch ......................... ✔
  2. Huỷ lệnh chờ (1 lệnh) ................. ✔  SEW-7b2c… CANCELED
  3. Đóng vị thế (1 vị thế) ................ ✔  BTCUSDT 0.002 → 0  (MARKET reduceOnly)
Hoàn tất. Kiểm chứng: exchange-status → Vị thế đang mở: 0
```

Và ca thất bại một phần — thứ **phải** nhìn thấy được, vì nó là lý do VO này không phải `bool`:

```text
  3. Đóng vị thế (1 vị thế) ................ ✘  APIError(-2019) Margin is insufficient
THẤT BẠI MỘT PHẦN — còn 1 vị thế đang mở. Giao dịch đã tắt, không có lệnh mới.
```

Script E2E `scripts/epic021k_emergency_stop_e2e.py` theo khuôn `backtest_timeframe_toolbar_e2e.py`
có sẵn, chạy offscreen để chụp lại được cả hai ca.

**Mốc 3 — marker:** sau một lệnh khớp thật, mở chart đúng symbol/khung → marker mũi tên xuất hiện
đúng nến và đúng giá khớp (so số với `exchange-status`).
