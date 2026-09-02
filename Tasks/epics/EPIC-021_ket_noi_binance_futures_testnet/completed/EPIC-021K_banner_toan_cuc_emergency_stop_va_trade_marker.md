# EPIC-021K — Banner môi trường toàn cục, Emergency Stop, trade marker trên chart

- **Trạng thái:** ✅ **Đã xong (2026-09-02)** — xem §6 "Kết quả xây dựng" cho danh sách file thật và
  phạm vi đã cắt có chủ đích.
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

---

## 6. Kết quả xây dựng (2026-09-02)

Cả 3 việc ở §1 đã dựng xong theo đúng thiết kế §2, đúng bảng file §3 (mở rộng thêm 2 file phát
sinh khi build). File thực tế đã ship:

| File | Việc |
| :--- | :--- |
| `src/domain/value_objects/venue_alignment.py` | **Mới** — `VenueAlignment` (3 trạng thái) + `compute_venue_alignment()`, đúng bảng §2.1 |
| `.../ui/components/environment_banner/{__init__,environment_banner_content,environment_banner}.py` | **Mới** — `EnvironmentBannerContent` (icon/message/severity) + `venue_alignment_banner_content()` (bảng nội dung đúng nguyên văn mock §2.1) + `EnvironmentBanner(Banner)` |
| `.../ui/kit/page_shell.py` | +`_environment_banner_factory` (class-level hook, `set_environment_banner_factory()`) — **một** chỗ sửa cho cả 5 màn, không đưa `VenueAlignment` vào `kit/` (kit/ không được biết khái niệm domain) |
| `src/presentation/ui/app_bootstrapper.py` | Tính `VenueAlignment` một lần lúc boot (`resolve_market_data_venue`/`resolve_trading_venue` đã có sẵn từ `EPIC-021`), đăng ký factory vào `PageShell` |
| `src/application/use_cases/trading/emergency_stop/{command,handler,result,__init__}.py` | **Mới** — 3 bước đúng thứ tự §2.2, mỗi bước tự bắt lỗi riêng, `EmergencyStopResult`/`EmergencyStopStepResult` không bao giờ là `bool` trần |
| `src/binance_bot_module.py` | +1 dòng đăng ký `EmergencyStopCommand` → `EmergencyStopCommandHandler` |
| `.../ui/screens/trading/{trading_view,trading_view_model,trading_presenter}.py` | Nút "DỪNG KHẨN CẤP" ở context bar (`StyleRole.DANGER_BUTTON`), **không** qua `@safe_ui_action` (đúng quyết định §2.2) — chia sẻ `ActionOwnershipTracker` với công tắc Bật/Tắt |
| `src/presentation/ui/common/order_fill_marker.py` | **Mới** — `OrderFilledEvent` → `MarkerPoint` (mua=xanh/lên, bán=đỏ/xuống, `reduce_only` → hậu tố "(Đóng)"), X lấy `order.order_time` (giờ sàn, `EPIC-021I`), fallback "now" |
| `.../ui/screens/trading/trading_presenter.py` | Nối `OrderFeed.orderFilled` → `order_filled_marker()` → `view.chart.set_script_markers()`, chỉ khi đúng symbol đang xem |
| `.../ui/screens/dashboard/dashboard_presenter.py` | **Mới, phát sinh khi build** — Dev Board nối cùng `OrderFeed`, vẽ marker trên đúng `ChartCard` theo symbol (đa-symbol, khác Trading màn chỉ có 1 chart) — xem §6.1 |
| `tests/unit/infrastructure/binance/test_order_submission_mode_live_is_restricted.py` | Mở rộng allowlist từ 1 file (`ExecuteOrderCommandHandler`) lên 2 (`EmergencyStopCommandHandler`) |

### 6.1 Phát sinh khi build: Dev Board cũng cần `OrderFeed`

Bảng file §3 chỉ ghi "`.../screens/backtest/logic/` + chart Dev Board | Nối `OrderFilledEvent` vào
trade marker" — soát lại thấy Dev Board **chưa từng** có bất kỳ subscription nào tới
`OrderFilledEvent`/`PositionChangedEvent` (không giống Trading màn, đã có `OrderFeed` từ
`EPIC-021H`/`EPIC-021I`). Dựng thêm đúng khuôn `TradingPresenter`'s wiring: `OrderFeed` là Feed đã
tồn tại sẵn (`presentation/ui/common/order_feed.py`), Dev Board chỉ là **người tiêu dùng thứ hai**
của cùng một Feed — không tạo thêm subscription trực tiếp nào (`test_one_event_is_not_subscribed_by_two_presenters`
chỉ quét `.on(...)` trong `screens/`, không quét việc dựng thêm một instance Feed, nên không đỏ).
Khác biệt duy nhất so với Trading: Dev Board đa-symbol, nên marker vẽ theo `active_charts.get(symbol)`
thay vì so sánh với một `_active_symbol` duy nhất — một fill cho symbol chưa mở chart bị bỏ qua lặng
lẽ (không có chart nào để vẽ vào).

### 6.2 Phạm vi đã cắt có chủ đích (ghi lại, không phải quên)

- **Script E2E `scripts/epic021k_emergency_stop_e2e.py`** (Mốc 2, §5) — không dựng trong lượt này.
  Khác các E2E khác trong repo (`backtest_timeframe_toolbar_e2e.py`, ~300 dòng), kịch bản này cần
  đặt trước 1 vị thế + 1 lệnh chờ thật trên testnet (`trade-once --live`) rồi mới có gì để bấm
  Emergency Stop — nghĩa là nó không tự chạy được trong CI/offscreen mà không có credentials
  testnet thật, khác hẳn vai trò một cổng CI. Bù lại: `TestOrdering`/`TestDisableTrading`/
  `TestCancelAllOrders`/`TestClosePositions`/`TestFullySucceeded` (§6.3 dưới) đã phủ đúng 2 ca Mốc 2
  mô tả (thành công đủ 3 bước, và thất bại một phần ở bước 3) ở tầng handler — chỉ thiếu phần
  "chạy thật, chụp màn hình" mà một script E2E mới làm được. Để dành cho một lượt riêng khi có
  credentials testnet sẵn sàng thao tác thủ công.
- **Integration test "bấm Emergency Stop khi có 2 lệnh chờ + 1 vị thế (fake server)"** (§4) — không
  dựng riêng một fake-server harness mới. Thay vào đó, `TestCancelAllOrders`/`TestClosePositions`
  trong `test_emergency_stop.py` đã dựng đúng ca "nhiều lệnh/nhiều vị thế, nhóm theo symbol" ở tầng
  `FuturesTradingClient` thật (chỉ mock `raw_client` bên dưới nó — cùng seam
  `test_execute_order.py` đã dùng), nên mã mapper/params thật đã chạy qua, chỉ không có socket
  thật. Quyết định này cùng lý do với gạch trên: dựng fake-server WebSocket/REST đầy đủ là việc
  ngoài phạm vi một lượt build, và giá trị tăng thêm so với `TestOrdering`'s `call_order` +
  `TestCancelAllOrders`/`TestClosePositions` là nhỏ.
- **"Integration: `OrderFilledEvent` → marker đúng vị trí thời gian/giá trên chart"** (§4) — thực
  hiện ở tầng Presenter thay vì tầng UI thật: `test_trading_presenter_toggle.py`/
  `test_dashboard_presenter.py` đều có test emit `OrderFilledEvent` thật qua `presenter._on_order_filled()`
  rồi assert `chart.set_script_markers()` được gọi đúng key + đúng `MarkerPoint` (đúng thời gian từ
  `order.order_time`, đúng giá từ `fill_price`) — phủ đúng đường đi Event → Presenter → Chart mà
  mục này đòi hỏi, chỉ khác "chart" ở đây là `MagicMock`/`mock_card` chứ không phải `ChartCard` thật
  đang vẽ pixel. `order_filled_marker()`'s 5 unit test riêng (`test_order_fill_marker.py`) đã phủ
  đúng phần tính toán (màu/label/hướng/thời gian) mà việc vẽ pixel thật không kiểm thêm được gì.
- **Màu sắc chính xác của banner** (xám/vàng/cam ở bảng §2.1) — không hardcode giá trị hex; ánh xạ
  sang `Severity.INFO`/`WARN`/`DANGER` đã có sẵn của `Banner` (bẫy 3, `ONBOARDING.md` §8 — không
  assert hằng số dễ trôi). `test_environment_banner_content.py` chỉ assert `message`/`icon`, không
  assert `severity` bằng string màu.

### 6.3 Kiểm thử

- **Unit (`VenueAlignment`):** `test_venue_alignment.py` (3 test — mỗi tổ hợp venue một kết quả).
- **Unit (banner content):** `test_environment_banner_content.py` (4 test — 3 trạng thái + không
  assert màu cứng), `test_environment_banner.py` (1 test — widget dựng đúng từ content).
- **Unit (`page_shell.py`):** 4 test mới trong `test_page_shell.py` — factory `None` → banner ẩn,
  factory có → banner hiện đúng widget, factory dùng chung cho nhiều `PageShell` (class-level, đúng
  ý "một chỗ sửa").
- **Integration (banner ở cả 5 màn):** `test_environment_banner_all_screens.py` — quét
  `real_screen_registry()` thật (giống `test_composition_root.py`'s
  `test_every_navigable_route_constructs`), không liệt kê tay 5 màn; parametrize theo route, mỗi
  View dựng xong tìm `findChild(QWidget, "environmentBanner")` khác `None`. Đúng đòi hỏi §4 "quét
  registry, không liệt kê tay".
- **Unit (Emergency Stop handler):** `test_emergency_stop.py` — `TestOrdering` (thứ tự 3 bước,
  **mutation-verify đã làm thật**: đảo bước 1/2 trong `handler.py`, chạy lại
  `test_steps_run_in_the_mandated_order` → đỏ đúng như kỳ vọng, sau đó revert nguyên văn — không
  giữ lại bản đảo), `TestDisableTrading`/`TestCancelAllOrders`/`TestClosePositions` (mỗi bước tự
  thành/bại độc lập, gộp theo symbol đúng cách `FuturesTradingClient.cancel_all_orders()` yêu cầu),
  `TestFullySucceeded` (bước 3 thất bại → `fully_succeeded is False`, không phải `bool` trần).
- **Unit (`order_filled_marker`):** `test_order_fill_marker.py` (5 test) — mua/bán đúng màu/hướng,
  `reduce_only` → hậu tố "(Đóng)", dùng `order.order_time` khi có, fallback "now" khi không.
- **Unit (Trading Presenter — Emergency Stop):** `test_trading_presenter_emergency_stop.py` (7
  test) — nút submit đúng worker, dispatch đúng command, thành công tắt trading + báo đúng, thất
  bại một phần báo đúng (không phải thành công), exception không làm chết slot, kết quả trễ của
  click cũ bị bỏ qua, và **guard riêng** cho quyết định "không `@safe_ui_action`": buộc
  `begin_action` tự nó raise, xác nhận lỗi vẫn lên `statusMessage` chứ không biến mất.
- **Unit (Trading/Dashboard Presenter — fill marker):** 2 test mới trong `test_trading_presenter_toggle.py`
  (marker vẽ đúng khi đúng symbol đang xem, không vẽ khi khác symbol) + 2 test mới trong
  `test_dashboard_presenter.py` (vẽ đúng vào đúng `ChartCard` theo symbol, không làm gì khi symbol
  chưa mở chart nào).
- **Guard mở rộng, giờ vẫn xanh:** `test_order_submission_mode_live_is_restricted.py` — allowlist
  2 file thay vì 1, cộng test tự-kiểm (`test_guard_actually_detects_a_violation`) xác nhận scanner
  vẫn bắt được vi phạm thật.
- Toàn bộ `ruff check`/`ruff format --check` sạch; `mypy` (`src` + `scripts`) sạch, 0 lỗi; cổng CI
  bắt buộc `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` chạy xanh sau khi sửa import order
  (ruff auto-fix): 3438 test (unit + integration) xanh, 4 skip (đúng nhóm `test_capture_screenshots`
  đã skip từ trước), sanity xanh, log scan sạch — 0 `FAILED`/`ERROR`/`Traceback`/`ResourceWarning`.
