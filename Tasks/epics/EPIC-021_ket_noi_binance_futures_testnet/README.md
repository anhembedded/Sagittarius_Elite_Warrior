# EPIC-021 — Kết nối Binance USD-M Futures Testnet & đường đi lệnh thật

- **Trạng thái:** 🟡 Đang làm (10/13 task con) — xem
  [`TRANG_THAI_va_LO_TRINH.md`](TRANG_THAI_va_LO_TRINH.md) cho Kanban, đồ thị phụ thuộc và Gantt
- **Ngày lập:** 2026-09-01
- **ADR bắt buộc đọc trước:** [`DECISION_2026-09-01_moi_truong_san_va_duong_di_lenh.md`](DECISION_2026-09-01_moi_truong_san_va_duong_di_lenh.md)
- **Sơ đồ:** [`design/`](design/) — 2 as-is, 2 to-be (**bản vẽ kế hoạch**, xem cảnh báo dưới)
- **📘 Chuyển giao kiến thức (người mới đọc file này trước) — viết bằng tiếng Anh theo yêu cầu:**
  [`KNOWLEDGE_TRANSFER_tu_0_den_hero.md`](KNOWLEDGE_TRANSFER_tu_0_den_hero.md) — testnet là gì,
  giao thức REST/WebSocket, component nào làm gì, đường đi một lệnh, 4 mốc CLI để bắt đầu dev.
  10 diagram PlantUML **as-built**, đã render kiểm chứng.

> ⚠️ `design/03_to_be_component.puml` vẽ `StrategyEngine → LiveTradingCoordinator` qua **event
> bus**. Đó là bản vẽ **trước khi code**; khi triển khai `EPIC-021G` phát hiện đường đó là lỗ
> hổng an toàn thật (backtest có thể bắn lệnh thật) và đã đổi sang lời gọi trực tiếp. Kiến trúc
> **as-built** nằm ở tài liệu chuyển giao kiến thức bên trên.

---

## 1. Vấn đề thật — đo trên code, không phải mô tả chung chung

Bot **chưa từng đặt một lệnh nào**, và khoảng cách tới chỗ đặt được không nằm ở "viết hàm
`create_order`". Nó nằm ở việc **app không có khái niệm môi trường sàn, cũng không có khái niệm
danh tính**. Sáu phát hiện dưới đây đều verify được bằng lệnh, không phải suy đoán:

| # | Phát hiện | Bằng chứng |
| :-: | :--- | :--- |
| **1** | DI dựng exchange client **không tham số** → luôn mainnet, luôn ẩn danh | [`binance_bot_module.py:231`](../../../src/binance_bot_module.py) `singleton(IExchangeClient, PythonBinanceClient)`, và ctor mặc định `Client(api_key="", api_secret="")` |
| **2** | Websocket cũng vậy | [`binance_websocket_service.py:110`](../../../src/infrastructure/binance/binance_websocket_service.py) `await AsyncClient.create()` |
| **3** | **API key user nhập ở Settings không bao giờ tới client** — UI nói dối | [`settings_presenter.py:139-140`](../../../src/presentation/ui/screens/settings/settings_presenter.py) ghi `API_KEY`/`API_SECRET` vào config; `grep` toàn `src/` không nơi nào đọc ra để dựng client → [`BUG-080`](../../bug_report/completed/BUG-080_settings_api_credentials_never_reach_the_exchange_client.md) |
| **4** | `BINANCE_REST_URL`/`BINANCE_WS_URL` là **config chết** | Khai ở [`config_keys.py:11-12`](../../../src/config/config_keys.py) + `app_config.json`, 0 nơi đọc trong `src/` → [`BUG-081`](../../bug_report/completed/BUG-081_binance_endpoint_config_keys_are_dead.md) |
| **5** | Không có port giao dịch nào | [`i_exchange_client.py`](../../../src/application/ports/i_exchange_client.py) có đúng 3 method market-data |
| **6** | Metadata sàn (stepSize/tickSize/minNotional) **có parser nhưng production không gọi** | `parse_binance_symbol_metadata` ([`market_metadata_parser.py:57`](../../../src/infrastructure/binance/market_metadata_parser.py)) chỉ được `tests/unit/.../test_market_metadata_parser.py` gọi |

Phát hiện 6 là cái nguy hiểm nhất về mặt "tưởng đã có": đặt lệnh futures **bắt buộc** làm tròn
khối lượng theo `stepSize` và kiểm `minNotional`, nếu không sàn trả `-1013`. Hạ tầng cho việc đó
đã tồn tại từ `BOT-095E1` — entity, parser, cache — và **chưa bao giờ được nối vào production**.

## 2. Cái đã có và tái dùng được — đừng viết lại

| Cần gì | Đã có sẵn |
| :--- | :--- |
| Sinh tín hiệu Buy/Sell/Short/Cover từ nến | [`StrategyEngine.on_tick()`](../../../src/application/services/strategy_engine.py) + `SignalGeneratedEvent` |
| Mô hình khớp lệnh, phí, slippage, margin, đòn bẩy | [`PaperExchange`](../../../src/domain/backtesting/paper_exchange.py) + 3 policy thuần domain |
| Chỗ hạ cánh cho tick live | [`MarketTickEventHandler`](../../../src/application/event_handlers/market_data/market_tick_event_handler.py) — hiện chỉ `logger.info()` |
| Metadata symbol | `SymbolMarketMetadata` + `ISymbolMarketMetadataCache` + parser |
| Test không chạm mạng | [`tests/sanity/binance_fake_server.py`](../../../tests/sanity/binance_fake_server.py) — server thật nói giao thức Binance |
| Đường event chuẩn hoá | `BaseEvent` + Feed pattern (`EPIC-008`) |
| Marker giao dịch trên chart | `BOT-009`'s Trade Markers Manager — **đang chờ đúng `OrderFilledEvent` mà epic này sinh ra** |

## 3. Mục tiêu

Kết thúc epic, một người dùng phải làm được đúng chuỗi này:

1. Nhập key Futures Testnet (qua biến môi trường, hoặc ô nhập ghi ra file **ngoài git**).
2. Bấm **Kiểm tra kết nối** → thấy số dư USDT testnet, position mode, margin type, độ lệch đồng hồ.
3. Chọn nguồn dữ liệu và nơi đặt lệnh **độc lập** trong Settings (ADR §2).
4. Bật giao dịch (mặc định **tắt**), chạy một chiến lược long-only hoặc có short, và thấy:
   lệnh được gửi → sàn xác nhận qua User Data Stream → vị thế hiện trên bảng → marker hiện trên chart.
5. Bấm **Emergency Stop** → mọi lệnh chờ bị huỷ, vị thế được đóng, giao dịch tắt.

**Ngoài phạm vi, cố ý:** giao dịch mainnet (ADR §3), COIN-M, Options, funding rate, mô hình
thanh lý (ADR §6).

## 4. Thứ tự thực hiện — xếp theo rủi ro tăng dần

Pha A không có bất kỳ đường đặt lệnh nào tồn tại trong code. Cuối pha A, thứ nguy hiểm nhất mà
app có thể làm là **đọc** số dư tài khoản testnet.

| # | Task | Repo | Chặn bởi | Trạng thái |
| :-: | :--- | :---: | :--- | :---: |
| **L** | [Đảo chiều phụ thuộc `qml/ → screens/` — điều kiện cần để màn Giao dịch dùng lại widget](completed/EPIC-021L_dao_chieu_phu_thuoc_qml_screens.md) | Elite | — (song song được) | ✅ (đóng `BUG-082`) |
| **A** | [Khái niệm môi trường sàn: `MarketDataVenue`/`TradingVenue` + client factory, cắt config chết](completed/EPIC-021A_khai_niem_moi_truong_san_va_client_factory.md) | Elite | — | ✅ (đóng `BUG-081`) |
| **B** | [Credentials: env-var trước, secret rời khỏi file git-tracked](completed/EPIC-021B_credentials_ngoai_git_va_khong_ro_ri_log.md) | Elite | A | ✅ (đóng 1/2 `BUG-080`) |
| **C** | [Metadata Futures vào production + policy làm tròn khối lượng/giá](completed/EPIC-021C_metadata_futures_va_policy_lam_tron.md) | Elite | A | ✅ |
| **D** | [Kiểm tra kết nối read-only — lần chạm sàn thật đầu tiên](completed/EPIC-021D_kiem_tra_ket_noi_read_only.md) | Elite | A, B | ✅ (đóng nốt `BUG-080`) |
| **E** | [Domain model lệnh sống + port `ITradingClient` (không chạm mạng)](completed/EPIC-021E_domain_model_lenh_song_va_port_trading.md) | Elite | C | ✅ |
| **F** | [Adapter `BinanceFuturesTradingClient` + dry-run qua `/fapi/v1/order/test`](completed/EPIC-021F_adapter_futures_va_dry_run.md) | Elite | D, E | ✅ |
| **G** | [`ExecuteOrderCommand` + `LiveTradingCoordinator` — lệnh thật đầu tiên, kèm hạn mức](completed/EPIC-021G_execute_order_command_va_live_coordinator.md) | Elite | F | ✅ |
| **H** | [User Data Stream: sự thật về lệnh đến từ sàn + `OrderFeed`](completed/EPIC-021H_user_data_stream_va_order_feed.md) | Elite | G | ✅ |
| **I** | [**Màn hình Giao dịch mới** — sổ lệnh, vị thế, công tắc bật giao dịch](completed/EPIC-021I_man_giao_dich_moi.md) | Elite | H | ✅ (mở `BUG-086`) |
| **K** | [Banner môi trường toàn cục + Emergency Stop + trade marker trên chart](completed/EPIC-021K_banner_toan_cuc_emergency_stop_va_trade_marker.md) | Elite | I | ✅ |
| **J** | [Tier `tests/testnet/` opt-in + fake server phục vụ endpoint futures](completed/EPIC-021J_tier_test_testnet_va_fake_server_futures.md) | Elite | F | ✅ |
| **M** | [Chart vốn (equity) realtime](incomplete/EPIC-021M_chart_von_realtime.md) | Elite | I | 🔴 |

**Không nhảy cóc.** `A` chặn tất cả vì mọi task sau đều cần biết "đang nói chuyện với sàn nào".
`C` chặn `E` vì không có `stepSize` thì `Order` không thể có khối lượng hợp lệ để mà mô hình hoá.
`J` có thể chạy song song với `G`–`I` sau khi `F` xong. `L` không phụ thuộc task nào trong epic — làm song song bất cứ lúc nào, miễn xong **trước** `I`.

Không có task nào thuộc repo **Engine** — toàn bộ cơ chế cần thiết (port, adapter, event bus,
Feed, task manager) đã tồn tại.

## 5. Mốc chạy được — mỗi task giao một thứ bấm/gõ được

Không task nào của epic này kết thúc bằng "code xong, test xanh". Mỗi task giao **một lệnh chạy
được và một thứ nhìn thấy được**. Chi tiết output mẫu nằm ở §5 của từng task file.

| Task | Gõ cái gì | Thấy cái gì |
| :-: | :--- | :--- |
| **A** | `scripts/epic021a_venue_probe.py` | 2 dòng URL **khác nhau** cho 2 venue + ping OK — bằng chứng config thật sự điều khiển endpoint (`BUG-081`) |
| **B** | `scripts/epic021b_credentials_probe.py` | Nguồn credentials đang thắng, key đã che, 4 đường rò rỉ đều sạch. Chạy được cả khi chưa có key |
| **C** | `scripts/epic021c_metadata_probe.py --qty 0.0137` | Policy làm tròn quyết định gì: `0.0137 → 0.013`, notional đủ/không đủ — **trước** khi có lệnh nào |
| **D** | `main.py exchange-status` | **Số dư USDT testnet thật của anh**, lệch đồng hồ, position mode. Lần chạm sàn đầu tiên |
| **E** | `main.py order-preview` | `Order` domain đã chuẩn hoá + `client_order_id`, hoặc lý do từ chối có tên (`MIN_NOTIONAL`) |
| **F** | `main.py order-dry-run` | *"Sàn CHẤP NHẬN payload. Không có lệnh nào được tạo."* — chữ ký + quyền + payload đúng, 0 lệnh khớp |
| **G** | `main.py trade-once --live` | **Lệnh khớp thật đầu tiên**, headless. Không `--live` thì dừng ở dry-run |
| **H** | `scripts/epic021h_user_stream_probe.py` (2 terminal) | Vòng đời `NEW → PARTIALLY_FILLED → FILLED` do **sàn** kể lại |
| **I** | `scripts/run-ui.ps1` → màn **Giao dịch** | Bảng vị thế/lệnh cập nhật ngay khi `trade-once` chạy ở terminal khác |
| **K** | Bấm **Dừng khẩn cấp** | 3 bước với dấu ✔/✘ từng bước, rồi `exchange-status` xác nhận `Vị thế đang mở: 0` |
| **J** | `ci-local.ps1 -TestnetOnly` | 3 test chạm sàn thật xanh; `-Full` **không** chạm file nào trong `tests/testnet/` |
| **L** | `python src/presentation/ui/qml/TradeLogTable/preview.py` | Widget bảng lệnh dựng độc lập, **0** import `screens.backtest` — guard `ast` xanh sau khi đỏ đúng 11 file trước đó |
| **M** | `trade-once --live` ở terminal khác, màn Giao dịch đang mở | Đường vốn nhích **một bước** đúng lúc lệnh khớp; đứng yên thì không sinh điểm mới |

Bốn task đầu (**A–D**) chạy được **hoàn toàn headless**, không cần GUI — đúng ràng buộc dual-mode
mà `README.md` của repo đặt ra từ đầu (chạy được trên VPS không màn hình). Giao diện chỉ vào cuộc
ở **I**/**K**, khi đã có thứ thật để hiển thị.

## 6. Màn hình: thêm đúng **một** màn mới

Câu hỏi "có cần thêm màn không" được trả lời tường minh ở [`EPIC-021I`](completed/EPIC-021I_man_giao_dich_moi.md) §1.1.
Tóm tắt quyết định:

| | Quyết định |
| :--- | :--- |
| **Màn Giao dịch** (mới) | ✅ Thêm. Vận hành liên tục (sổ lệnh, vị thế, công tắc) — không nhét vào Dev Board, vì Dev Board theo `BOT-014` là màn *debug*, và `EPIC-003` đang mở **vì** Presenter quá tải |
| **Banner môi trường** | ❌ Không phải màn. Là header của `PageShell` → tự có ở **cả 5** màn (`EPIC-021K`) |
| **Settings** | ❌ Không thêm màn. Giữ nguyên vai trò: credentials + chọn venue + Kiểm tra kết nối (`EPIC-021D`) |
| **Chart** | ❌ Không thêm màn. Chỉ nối `OrderFilledEvent` vào Trade Markers mà `BOT-009` đã để dở |

Chi phí một màn mới ở repo này gần bằng 0 kể từ `EPIC-016`: một `AbstractScreenModule` con **+ một
dòng** trong `app_bootstrapper.py:285-288`; `MainWindow` không đổi dòng nào. Tầng Sanity cũng
**không phát sinh test mới** — `testing-rule.md` §1 quy định tier đó quét nguồn sự thật chứ không
liệt kê từng màn.

## 7. Bug đi kèm phải mở trước khi sửa

Hai phát hiện #3 và #4 ở §1 là **phát biểu sai sự thật của code với người dùng và với chính agent
đọc nó** — theo luật repo, đó là BUG, không phải "tiện tay dọn trong lúc làm feature":

- [`BUG-080`](../../bug_report/completed/BUG-080_settings_api_credentials_never_reach_the_exchange_client.md) — đóng: `EPIC-021B` (lưu trữ an toàn) + `EPIC-021D` (client thật sự ký request)
- [`BUG-081`](../../bug_report/completed/BUG-081_binance_endpoint_config_keys_are_dead.md) — đóng bởi `EPIC-021A`
- [`BUG-082`](../../bug_report/completed/BUG-082_shared_qml_widget_library_depends_on_screen_modules.md) — thư viện widget dùng chung phụ thuộc ngược vào màn hình; đóng bởi `EPIC-021L`

## 8. Rủi ro đã biết

| Rủi ro | Xử lý |
| :--- | :--- |
| Key testnet bị reset định kỳ → 401 trông như lỗi cấu hình | `EPIC-021D` phân biệt tường minh 3 nhóm lỗi: chưa cấu hình / sai chữ ký / key hết hạn |
| Giá testnet lệch giá mainnet mà chart đang hiển thị | Cảnh báo thường trực khi hai venue lệch nhau (ADR §2.2), và `VenueAlignment` là một type, không phải một dòng chữ |
| Tài khoản testnet bị đổi bởi tác nhân khác (web, phiên app khác) | Reconciliation lúc khởi động + User Data Stream là nguồn sự thật (ADR §4) |
| Một vòng lặp tín hiệu lỗi bắn hàng trăm lệnh | Hạn mức cứng trong `EPIC-021G`: số lệnh/phiên, notional tối đa, 1 vị thế/symbol, kill switch |
| `logger.info()` mỗi lệnh làm đơ UI | Đã có tiền lệ thật `BUG-042` (838 trade → 5.028 dòng log → UI đơ). Đường log lệnh phải `DEBUG` hoặc throttle ngay từ `EPIC-021G` |
| Hedge mode bật sẵn trên tài khoản testnet → mọi giả định One-way sai | `EPIC-021D` **từ chối tường minh** khi phát hiện Hedge mode, không chạy tiếp |
