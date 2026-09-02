# EPIC-021I — Màn hình **Giao dịch** mới (sổ lệnh, vị thế, công tắc)

- **Trạng thái:** 🔴 Chưa bắt đầu
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021H` · **Chặn:** `EPIC-021K`

---

## 1. Bối cảnh & vấn đề thật

Từ `EPIC-021D` đến `EPIC-021H`, mọi thứ chạy được bằng CLI headless. Đó là chủ ý — nhưng nó dừng
đúng ở chỗ một người vận hành cần **nhìn liên tục**: lệnh nào đang chờ, vị thế nào đang mở, PnL
chưa thực hiện bao nhiêu, giá thanh lý ở đâu. Không ai chạy `exchange-status` mỗi 10 giây.

### 1.1 Vì sao là màn **mới**, không nhét vào Dev Board

Câu hỏi này đáng trả lời tường minh vì "thêm màn hình" thường là phản xạ sai. Ở đây có bốn lý do
cụ thể của repo này:

1. **Dev Board là màn *dev*, theo đúng định nghĩa của chính nó.** `BOT-014` lập ra nó để
   *"Dashboard mặc định chỉ hiện 1 chart `ETHUSDT`, để tập trung test/debug thay vì phân tán"*.
   Giao dịch thật không phải mối quan tâm debug.
2. **`EPIC-003` vẫn đang mở vì Presenter quá tải** ("Phân rã Presenter/File quá tải"). Nhồi sổ
   lệnh + vị thế + công tắc + reconciliation vào `DashboardPresenter` là đi thẳng vào vấn đề mà
   một epic đang mở tồn tại để sửa.
3. **Chi phí thêm màn đã gần bằng 0 từ `EPIC-016`.** Screen Registry Pattern khiến một màn mới =
   một `AbstractScreenModule` con (route/title/icon/location/sequence + 2 factory method) **+ đúng
   một dòng** trong danh sách ở `app_bootstrapper.py:285-288`. `MainWindow` **không đổi một dòng
   nào** — đó chính là điều `EPIC-016` được làm ra để đạt được.
4. **Tầng Sanity không phát sinh test nào.** `testing-rule.md` §1: *"Adding a feature/screen adds
   zero new tests to `tests/sanity/`"* — mọi assertion ở tier đó **quét** nguồn sự thật (mọi use
   case đã đăng ký, mọi route điều hướng được, mọi package màn hình trên đĩa) chứ không liệt kê
   tay. Màn mới tự động được phủ.

Ngược lại, thứ **không** được tách ra màn riêng: **banner môi trường**. Nó là trạng thái toàn hệ
thống, phải thấy ở mọi màn — thuộc header của `PageShell` (`EPIC-021K`).

Và Settings **giữ nguyên vai trò**: credentials + chọn venue + nút Kiểm tra kết nối (`EPIC-021D`).
Đó là cấu hình, không phải vận hành. Hai thứ khác nhịp sử dụng: cấu hình một lần, vận hành liên tục.

## 1.2 Prompt thiết kế

Trước khi code bố cục: [`design/PROMPT_thiet_ke_man_giao_dich.md`](../design/PROMPT_thiet_ke_man_giao_dich.md)
— prompt tự chứa để nhờ một AI thiết kế dựng mockup 3 trạng thái (giao dịch tắt / đang chạy /
Dừng khẩn cấp thất bại một phần). Nó mang sẵn đúng palette, font, và luật 4 dải của `PageShell`
lấy từ code thật.

> **Đã có mockup (2026-09-01).** User đã dựng xong bản thiết kế và sẽ cung cấp khi bắt tay vào
> task này. **Hỏi user trước, đừng tự sinh lại bằng prompt trên** — prompt đó giờ chỉ còn là bản
> ghi các ràng buộc đã đặt ra, không phải bước cần chạy lại.
>
> **Cập nhật 2026-09-02 — review mockup trạng thái A:** thiếu chart giá realtime và chart vốn.
> Prompt yêu cầu vẽ bổ sung: [`PROMPT_cap_nhat_mock_them_chart.md`](../design/PROMPT_cap_nhat_mock_them_chart.md).
> Chart giá vào task này (§2.2b); chart vốn tách sang [`EPIC-021M`](EPIC-021M_chart_von_realtime.md).

Mockup là **đầu vào**, không phải hợp đồng: widget vẫn lấy từ `kit/` và `qml/` đã có, không dựng
widget mới chỉ vì mockup vẽ khác. Đối chiếu mockup với ảnh chụp app thật **sau** khi dựng xong —
đúng cách `EPIC-020` phát hiện được 4 lỗi bố cục.

## 2. Thiết kế + lý do

### 2.1 Đăng ký màn — đúng khuôn `EPIC-016`, không phát minh gì

```python
# src/presentation/ui/screens/trading/module.py
class TradingScreenModule(AbstractScreenModule):
    route = "trading"
    title = "Giao dịch"
    icon = "candlestick-chart"        # bộ Lucide đã có (BOT-016)
    location = NavLocation.MAIN
    item_sequence = 25                # sau Dev Board, trước Backtest
```

Cộng một dòng trong danh sách module ở `app_bootstrapper.py`. Hết.

### 2.2 Bố cục — `PageShell` 4 dải, không tự dựng layout

`EPIC-020` đã chốt hình dạng và áp cho cả 4 màn hiện có. Màn thứ 5 dùng lại:

| Dải | Nội dung |
| :--- | :--- |
| **Header** | Tiêu đề màn + (banner môi trường cắm vào ở `EPIC-021K`) |
| **Context bar** | Chọn symbol (`SymbolPicker` dùng chung — `EPIC-014`), công tắc **Bật giao dịch**, trạng thái kết nối rút gọn |
| **Workspace** | **Chart realtime** (trên — §2.2b) + bảng **Vị thế đang mở** + bảng **Lệnh đang chờ** |
| **Rail phải** | Thẻ tài khoản: số dư USDT, margin đã dùng, PnL chưa thực hiện, số lệnh đã đặt trong phiên / hạn mức |
| **Console** | Nhật ký lệnh của riêng màn này |

### 2.2b Chart realtime — theo khuôn Dev Board, **không** kéo `screens/backtest/` vào

> **Bổ sung 2026-09-02 (user review mockup).** Mockup trạng thái A không có chart. User yêu cầu
> thêm **chart realtime kèm chiến lược**. Chart **vốn (equity)** tách sang [`EPIC-021M`](EPIC-021M_chart_von_realtime.md).

Đã đo trước khi quyết định, không suy đoán:

| Câu hỏi | Đo được gì |
| :--- | :--- |
| `ChartCard` có phụ thuộc màn nào không? | **Không.** `components/chart_card/` không import `screens/` — dùng lại trực tiếp được |
| Có tiền lệ chart realtime nào chưa? | **Có.** Dev Board (`screens/dashboard/dashboard_view.py:135`) dựng thẳng `ChartCard`, và **không** import `screens/backtest/` (chỉ một docstring nhắc tên, không phải import) |
| Dùng lại `chart_canvas_view.py` của backtest được không? | **Không, và không nên.** `trade_flag_markers(result: BacktestResult)` nhận thẳng `BacktestResult`; `equity_curve_to_*` nhận equity curve của backtest. Chúng gắn với kiểu dữ liệu backtest, không phải "chart logic dùng chung" |

**Kết luận:** đi theo khuôn Dev Board — `ChartCard` + một `indicator_coordinator` riêng của màn Giao
dịch. **Không** cần trích xuất module nào ra khỏi `screens/backtest/`, nên **không** tái tạo chiều
phụ thuộc mà `EPIC-021L` vừa đảo xong (`BUG-082`). Nếu về sau thấy cần dùng chung thật, đó là một
task trích xuất riêng, không phải việc làm kèm ở đây.

**Nguồn dữ liệu chart:** nến đến từ `MarketDataVenue.MAINNET_PUBLIC` (đường đã có sẵn, dùng chung
với Dev Board/Backtest) — **không** phải từ testnet. Đây chính là chỗ giá hiển thị ≠ giá khớp mà
`EPIC-021K`'s banner phải nói ra (ADR §2.2).

**Ngoài phạm vi task này:** marker Buy/Sell của **lệnh thật** vẽ lên chart — thuộc `EPIC-021K`
("trade marker trên chart"), vì nó tiêu thụ `OrderFilledEvent` chứ không phải nến.

### 2.3 Widget QML + ViewModel test được không cần GUI

Đúng khuôn `EPIC-015` đã đo và chốt: widget ở thư mục riêng, ViewModel test riêng. Dùng lại hình
dạng bảng của `DatabaseStatusTable`/`KlineInspectorTable`, **kèm bài học `BUG-076`**: mọi cột chuỗi
dài (thời gian, `client_order_id`) phải có `elide: Text.ElideRight` **và** `Layout.minimumWidth: 0`
— thiếu cái thứ hai thì `elide` vô hiệu trong `RowLayout`.

### 2.4 Dữ liệu **chỉ** đến từ `OrderFeed`

Màn này không nghe bus trực tiếp, không tự gọi `ITradingClient`. `EPIC-021H` đã dựng đúng một
subscriber chuẩn hoá; màn hình là nơi *hiển thị*, theo `architecture-rule.md` §6.

Hệ quả kiểm chứng được: mở màn với giao dịch tắt → bảng rỗng, **không** phát request nào.

### 2.5 Công tắc "Bật giao dịch" là hành động có hệ quả, không phải một checkbox

Bật → chạy reconciliation của `EPIC-021G` (đọc vị thế/lệnh thật) **trước khi** cho phép lệnh đầu
tiên; nếu sàn có vị thế mà app không biết → hiện ra và **từ chối bật**, để user quyết định. Trạng
thái công tắc **không** được nhớ qua lần khởi động (ngoại lệ có chủ đích với `EPIC-010` — mở app
lên không bao giờ tự ở trạng thái sẵn sàng đặt lệnh).

## 3. Thay đổi theo từng file

| File | Việc |
| :--- | :--- |
| `.../ui/screens/trading/module.py` | **Mới** — `TradingScreenModule` |
| `.../ui/screens/trading/trading_view.py` | **Mới** — dựng `PageShell` 4 dải |
| `.../ui/screens/trading/trading_presenter.py` | **Mới** — nối `OrderFeed`, công tắc, reconciliation |
| `.../ui/screens/trading/i_trading_view.py` | **Mới** — hợp đồng Presenter↔View **tường minh** (§2.1 `architecture-rule.md`), kèm test hai chiều theo khuôn `EPIC-013B` |
| `.../ui/screens/trading/view_models/` | **Mới** — ViewModel cho 2 bảng + thẻ tài khoản |
| `.../ui/screens/trading/qml/` | **Mới** — `PositionsTable.qml`, `OpenOrdersTable.qml`, `AccountCard.qml` |
| `.../ui/screens/trading/coordinators/chart_coordinator.py` | **Mới** — nối `ChartCard` + đường chỉ báo chiến lược, theo khuôn `screens/dashboard/coordinators/indicator_coordinator.py` (§2.2b) |
| `src/presentation/ui/app_bootstrapper.py` | **+1 dòng** trong danh sách screen module |

### 3.1 Hai lỗ hổng dữ liệu phát hiện khi đọc mockup (2026-09-02)

Đối chiếu từng cột của mockup với domain model thật:

| Bảng | Kết quả đối chiếu |
| :--- | :--- |
| **Vị thế** | ✅ Mọi cột map được. `HƯỚNG` = dấu của `position_amt`, `KHỐI LƯỢNG` = `abs(position_amt)` — **suy ra**, không phải field lưu sẵn |
| **Lệnh chờ** | ⚠️ Cột `THỜI GIAN` **không có nguồn**. `Order` không có field thời gian, và `map_futures_order_payload_to_order()` không đọc `time`/`updateTime` của Binance |

**Chốt: dùng thời gian của sàn** — thêm field vào `Order`, map từ `time`/`updateTime` của payload.

Lý do chọn (a) thay vì đóng dấu thời gian ở tầng presentation lúc gửi:

- ADR §4 đã đặt nguyên tắc "sự thật đến từ sàn". Một cột thời gian do app tự đóng dấu sẽ **lệch**
  với thời gian sàn ghi nhận, và lệch bao nhiêu thì không ai biết — đúng loại nửa-sự-thật mà epic
  này tồn tại để loại bỏ.
- `LivePosition` **đã có** `updated_at` lấy từ `updateTime` của sàn. Để `Order` không có gì tương
  đương là bất đối xứng vô cớ giữa hai entity cạnh nhau.
- Khi đối chiếu một lệnh với nhật ký hoặc với lịch sử trên web Binance, thứ khớp được là **thời
  gian sàn**, không phải giờ máy người dùng.

Chi phí: thêm một field `Optional` vào `Order` (frozen dataclass) + một dòng trong
`map_futures_order_payload_to_order`. Field phải là **optional**: `Order` được app dựng **trước
khi** gửi, lúc đó sàn chưa cấp thời gian nào — cùng lý do `LivePosition.updated_at` có nhánh
fallback.

## 4. Kiểm thử

- **Unit (ViewModel):** 2 bảng render đúng từ dữ liệu `OrderFeed`; bảng rỗng khi chưa có gì (không
  phải crash, không phải hàng giả).
- **Unit (hợp đồng):** test `ast` hai chiều cho `ITradingView` — thành viên dùng mà chưa khai
  **và** khai mà không ai dùng đều đỏ, có khoá cả số đếm (`EPIC-013B`).
- **Unit:** bật công tắc khi reconciliation thấy vị thế lạ → công tắc **không** bật lên.
- **Integration:** `OrderFilledEvent` qua `OrderFeed` → dòng xuất hiện đúng ở bảng vị thế.
- **Sanity:** màn mới được tier quét tự động phát hiện; boot im lặng (`diagnostic_guard`), **0 test
  sanity mới được viết** — nếu phải viết thì test sanity cũ đã sai thiết kế.

## 5. Mốc chạy được

Chạy app thật và mở màn mới:

```bash
pwsh -NoProfile -File scripts/run-ui.ps1
# hoặc headless để chụp ảnh: QT_QPA_PLATFORM=offscreen + script E2E khuôn
# scripts/backtest_timeframe_toolbar_e2e.py
```

Nhìn thấy được, với một vị thế đặt sẵn bằng `trade-once --live` từ `EPIC-021G`:

```text
Sidebar: [Dev Board] [Giao dịch] ← mới  [Backtest] [Database] … [Settings]

Giao dịch                              Bật giao dịch: [ TẮT ]   Kết nối: ✔ FUTURES_TESTNET
─────────────────────────────────────────────────────────────────────────────
VỊ THẾ ĐANG MỞ                                        │ TÀI KHOẢN
 BTCUSDT  LONG  0.002  entry 64,105.35  uPnL -0.02    │  USDT khả dụng  14,871.6
                       liq 32,140.00                  │  Margin đã dùng    128.2
LỆNH ĐANG CHỜ                                         │  PnL chưa TH       -0.02
 (không có)                                           │  Lệnh phiên này    1 / 20
```

Ba thứ chứng minh mốc này **thật sự chạy**, không phải khung rỗng: số liệu khớp với
`exchange-status` của `EPIC-021D`; bảng cập nhật **ngay** khi `trade-once --live` chạy ở terminal
khác (qua `OrderFeed`, không phải poll); và mở màn với giao dịch tắt thì **không** có request nào
rời máy.
