# EPIC-021I — Màn hình **Giao dịch** mới (sổ lệnh, vị thế, công tắc)

- **Trạng thái:** 🟢 **Sẵn sàng bắt đầu (2026-09-02)** — mock đã duyệt (§3.4: 3/4 mục đạt;
  5 trạng thái ở §2 prompt vòng 3 tổng quát hoá từ pattern có sẵn trong mock, không cần vòng mock
  thứ 4). [`BOT-124`](../../../completed/BOT-124_trich_datatable_dung_chung_cho_qml.md) đã xong —
  `DataTable.qml` dùng chung sẵn sàng cho 2 bảng của màn này. Không còn gì chặn code.
- **Repo:** Elite
- **Chặn bởi:** `EPIC-021H` ✅ · `BOT-124` ✅ · **Chặn:** `EPIC-021K`

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

Đúng khuôn `EPIC-015` đã đo và chốt: widget ở thư mục riêng, ViewModel test riêng.

> **Sửa 2026-09-02:** câu gốc ở đây viết *"dùng lại **hình dạng** bảng của
> `DatabaseStatusTable`/`KlineInspectorTable`"* — mà "dùng lại hình dạng" chính là viết bản sao
> gần giống, đúng thứ `qml-rule.md` §0.2 cấm. Xem §3.2.2:
> repo đã có **3** bản sao của cùng một khung bảng; chọn tổng quát hoá hay viết tiếp bản sao thứ
> 4/5 là quyết định chưa chốt, chờ user.

**Bài học `BUG-076` giữ nguyên** dù chọn hướng nào: mọi cột chuỗi dài (thời gian,
`client_order_id`) phải có `elide: Text.ElideRight` **và** `Layout.minimumWidth: 0` — thiếu cái
thứ hai thì `elide` vô hiệu trong `RowLayout`.

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

> **Sửa 2026-09-02 sau khi đối chiếu 3 file luật UI — xem §3.2 cho từng chỗ và bằng chứng.**
> Bảng dưới đây **đã** là bản đã sửa; bảng cũ (có `view_models/`, `qml/` riêng của màn, hai
> `.qml` bảng mới) vi phạm 3 luật và được giữ nguyên văn trong §3.2 để biết đã sửa cái gì.

| File | Việc |
| :--- | :--- |
| `.../ui/screens/trading/module.py` | **Mới** — `TradingScreenModule` |
| `.../ui/screens/trading/trading_view.py` | **Mới** — dựng `PageShell` 4 dải (QtWidgets — bắt buộc, xem §3.2.1) |
| `.../ui/screens/trading/trading_presenter.py` | **Mới** — nối `OrderFeed`, công tắc, reconciliation; **giữ toàn bộ** action-ownership/cancellation (§3.2.3) |
| `.../ui/screens/trading/trading_view_model.py` | **Mới** — ViewModel của màn, **phẳng ở gốc thư mục** (MVP trio) |
| `.../ui/screens/trading/i_trading_view.py` | **Mới** — hợp đồng Presenter↔View **tường minh** (§2.1 `architecture-rule.md`), kèm test hai chiều theo khuôn `EPIC-013B` |
| `.../ui/screens/trading/preview.py` | **Mới** — `build_preview() -> QWidget`, **bắt buộc**, guard test chặn nếu thiếu (§3.2.4) |
| `.../ui/screens/trading/coordinators/chart_coordinator.py` | **Mới** — nối `ChartCard` + đường chỉ báo chiến lược, theo khuôn `screens/dashboard/coordinators/indicator_coordinator.py` (§2.2b). **Không** giữ `action_id`/huỷ tác vụ của riêng nó (§3.2.3) |
| `src/presentation/ui/qml/DataTable/` | **Đã có** ([`BOT-124`](../../../completed/BOT-124_trich_datatable_dung_chung_cho_qml.md)) — bảng vị thế/lệnh chờ dựng **trên** component dùng chung đó, ở thư viện dùng chung, **không** ở `screens/trading/qml/` (§3.2.2) |
| `src/presentation/ui/app_bootstrapper.py` | **+1 dòng** trong danh sách screen module |

### 3.1 Hai lỗ hổng dữ liệu phát hiện khi đọc mockup (2026-09-02)

Đối chiếu từng cột của mockup với domain model thật:

| Bảng | Kết quả đối chiếu |
| :--- | :--- |
| **Vị thế** | ✅ Mọi cột map được. `HƯỚNG` = dấu của `position_amt`, `KHỐI LƯỢNG` = `abs(position_amt)` — **suy ra**, không phải field lưu sẵn |
| **Lệnh chờ** | ⚠️ Cột `THỜI GIAN` **chưa có nguồn trong code**. `Order` không có field thời gian; `map_futures_order_payload_to_order()` không đọc `time`/`updateTime`, và `parse_order_trade_update()` không đọc `"T"` — dữ liệu **có** trên dây, đang bị vứt đi (cùng hình dạng với lỗ hổng `"B"`/số dư ở `EPIC-021M`) |

> ✅ **CHỐT: dùng thời gian của sàn (phương án a).** Quyết định của agent theo
> [`ONBOARDING.md`](../../../../.agents/ONBOARDING.md) §7 — *"khi nhiều hướng đều hợp lý và không
> có câu trả lời tuyệt đối đúng → quyết theo best practice / pattern đã được kiểm chứng"*, và chỉ
> hỏi user khi rơi vào đúng 1 trong 3 nhóm (đánh đổi lớn/không đảo ngược được · nằm trong bảng
> "phải hỏi" · thiếu thông tin chỉ user mới có). Đây không thuộc nhóm nào: thêm một field
> `Optional` vào một entity là đảo ngược được, và §7 nói rõ *"agent quyết và đi tiếp"*.
>
> **Ghi lại một sai lầm về quy trình, vì nó có ích hơn là xoá đi:** bản trước của file này chốt
> (a), rồi tôi **hoàn tác** nó, viện
> [`domain-truth-rule.md`](../../../../.agents/rules/domain-truth-rule.md)'s *Counterintuitive
> Story Check*. Đọc lại thì luật đó nói **"stop and report the observable behavior, evidence, and
> trade-off"** — nó buộc phải **trình bày** bằng chứng và đánh đổi, **không** buộc dừng lại chờ
> user. Tôi đã biến "báo cáo rồi quyết" thành "chặn lại rồi chờ" — leo thang một quyết định thuộc
> thẩm quyền của mình. Bảng đánh đổi + 3 bằng chứng dưới đây chính là phần "report" mà luật đòi;
> giữ nguyên, chỉ đổi kết luận từ *đề xuất* thành *đã chốt*.

**Hai phương án đã cân, chốt (a):**

| | (a) Thời gian của **sàn** | (b) Đóng dấu ở **presentation** lúc gửi |
| :--- | :--- | :--- |
| Nguồn | `time`/`updateTime` trong payload Binance | `datetime.now()` của máy chạy app |
| Chi phí | Thêm 1 field `Optional` vào `Order` (frozen dataclass) + 1 dòng trong `map_futures_order_payload_to_order` | Không đụng domain |
| Đối chiếu với lịch sử trên web Binance | Khớp | **Không khớp** (lệch bao nhiêu không ai biết) |

**Ba bằng chứng dẫn tới (a):**

- ADR §4 đã đặt nguyên tắc "sự thật đến từ sàn". Một cột thời gian do app tự đóng dấu sẽ **lệch**
  với thời gian sàn ghi nhận, và lệch bao nhiêu thì không ai biết — đúng loại nửa-sự-thật mà epic
  này tồn tại để loại bỏ.
- `LivePosition` **đã có** `updated_at` lấy từ `updateTime` của sàn. Để `Order` không có gì tương
  đương là bất đối xứng vô cớ giữa hai entity cạnh nhau.
- Khi đối chiếu một lệnh với nhật ký hoặc với lịch sử trên web Binance, thứ khớp được là **thời
  gian sàn**, không phải giờ máy người dùng.

Nếu chọn (a): field **bắt buộc là `Optional`** — `Order` được app dựng **trước khi** gửi, lúc đó
sàn chưa cấp thời gian nào (cùng lý do `LivePosition.updated_at` có nhánh fallback).

### 3.2 Đối chiếu với luật UI (2026-09-02) — 4 chỗ kế hoạch cũ sai

Kế hoạch này viết trước khi đọc hết `.agents/rules/`. Đối chiếu lại với `qml-rule.md`,
`async-ui-action-rule.md`, `ui-presentation-rule.md` thì bảng file cũ sai 4 chỗ. Bảng cũ nguyên
văn, để so:

```text
| .../ui/screens/trading/view_models/                    | ViewModel cho 2 bảng + thẻ tài khoản          |
| .../ui/screens/trading/qml/                            | PositionsTable.qml, OpenOrdersTable.qml,      |
|                                                        | AccountCard.qml                               |
| .../ui/screens/trading/coordinators/chart_coordinator.py | nối ChartCard + đường chỉ báo chiến lược    |
```

#### 3.2.1 Container của màn **phải** là QtWidgets — ràng buộc, không phải sở thích

`qml-rule.md` §0: *"QML lồng được vào QtWidgets. Chiều ngược lại Qt không hỗ trợ"*, nên
*"cái gì chứa chart thì phải là QtWidgets"* — chart là pyqtgraph (`QGraphicsView`, thuần
QtWidgets), và §2.2b vừa quyết định đặt chart realtime vào dải Workspace của màn này.

Đã kiểm: `PageShell` (`src/presentation/ui/kit/page_shell.py:51`) là `class PageShell(QWidget)` —
QtWidgets thật. Nên §2.2 đã đúng sẵn; ghi ra đây để lần sau không ai "hiện đại hoá" màn này thành
một `QQuickWidget` toàn phần rồi phát hiện chart không lồng vào được. Hình "cả route là QML" ở
bảng §0 của `qml-rule` **không** áp dụng được cho màn có chart.

#### 3.2.2 Hai `.qml` bảng mới — vi phạm §0.2, và repo đã có 3 bản sao gần giống

`qml-rule.md` §0.2: *"Cái gì dùng chung được thì phải dựng dùng chung, không viết bản sao 'gần
giống'. […] Một hình 'gần giống nhưng hơi khác' là tín hiệu để **tổng quát hoá** component có
sẵn"*.

Đo thật, không suy đoán — 3 bảng đã có trong `src/presentation/ui/qml/`:

| Widget | `.qml` bảng | Row delegate |
| :--- | ---: | ---: |
| `TradeLogTable` | 141 dòng | 245 dòng |
| `KlineInspectorTable` | 139 dòng | 112 dòng |
| `DatabaseStatusTable` | 140 dòng | 148 dòng |

Cả ba cùng một khung: root `ColumnLayout` → `readonly property int <x>ColumnWidth` → `PanelHeader`
→ `RowLayout` nhãn cột → `Rectangle` kẻ ngang → `ListView` → `Text` trạng thái rỗng. Phần đuôi
gần như giống từng ký tự — `TradeLogTable.qml:111-141` và `KlineInspectorTable.qml:109-139` chỉ
khác `objectName`, kiểu delegate, tên property bề rộng cột, và câu chữ dòng rỗng.

Viết thêm `PositionsTable.qml` + `OpenOrdersTable.qml` sẽ thành bản sao thứ **4** và **5** của
đúng khung đó. §0.2 nói rõ đây là lúc phải tổng quát hoá.

**✅ CHỐT: hướng A — trích một `DataTable` dùng chung, làm ở [`BOT-124`](../../../completed/BOT-124_trich_datatable_dung_chung_cho_qml.md) trước, `EPIC-021I` tiêu thụ nó.**

| Hướng | Được | Mất |
| :--- | :--- | :--- |
| **A. (chốt)** Trích một `DataTable` dùng chung (header + cột + `ListView` + trạng thái rỗng), 3 bảng cũ chuyển sang dùng, 2 bảng mới dùng luôn | Xoá ~3 bản sao; bảng thứ 6 sau này gần như miễn phí | Đụng 3 widget đang chạy thật ⇒ tách thành task riêng, không làm kèm ở đây |
| **B.** Viết 2 bảng mới theo đúng khung cũ, ghi nợ kỹ thuật, tổng quát hoá sau | `EPIC-021I` không bị chặn ngay | Bản sao 4 và 5; càng nhiều bản sao thì việc trích xuất sau càng đắt — đúng cơ chế đã sinh ra `BUG-082` |

**Vì sao agent tự chốt, không hỏi:** [`ONBOARDING.md`](../../../../.agents/ONBOARDING.md) §7 chỉ
buộc hỏi khi (1) đánh đổi lớn/không đảo ngược được, (2) nằm trong bảng "phải hỏi", hoặc (3) thiếu
thông tin chỉ user mới có. Không cái nào đúng ở đây, và §7 còn nói thẳng theo chiều ngược lại:
*"đừng ngại redesign một phần đã có nếu thiết kế hiện tại là hard design… **'nó đang chạy được'
không phải lý do để yên đó**"*. Bản trước của file này để ngỏ với lý do "mở một task tái cấu trúc
là quyết định phạm vi của user" — đó là leo thang, không phải thận trọng.

Thực ra hướng đi **đã được luật quyết sẵn**, không phải hai lựa chọn ngang nhau: `qml-rule.md`
§0.2 nói *"một hình 'gần giống nhưng hơi khác' là tín hiệu để **tổng quát hoá** component có
sẵn"*, và nêu tiền lệ có thật — `SelectListVM` đã hấp thụ `TimezonePickerVM`, **xoá** bản gốc chứ
không giữ lại làm forwarder. Câu hỏi duy nhất còn lại là **xếp việc**, mà đó là phán đoán kế hoạch
bình thường: trích trước, tiêu thụ sau, vì `BOT-124` chạm 3 widget đang chạy và trộn nó vào
`EPIC-021I` sẽ khiến một hồi quy UI không phân biệt được là do trích xuất hay do màn mới.

**Đã chốt được, độc lập với A/B:** chỗ đặt. `qml-rule.md` §0.2 (quyết định user 2026-08-29) đặt
`src/presentation/ui/qml/` là **nơi chính thức** dựng QML component. `screens/trading/qml/` sẽ là
nhà thứ hai cho QML — đúng kiểu phân mảnh mà `EPIC-021L`/`BUG-082` vừa dọn xong.

**`AccountCard.qml` thì bỏ hẳn.** Rail tài khoản là 4-6 ô số chỉ đọc, không tương tác — đúng ô
*"Lưới thẻ chỉ đọc → `StatGrid`"* trong bảng component dùng chung ở `qml-rule.md` §2 (`StatCardRow`
cũng đã có). Viết một `.qml` mới cho hình đã có component là đúng điều §2 bảo kiểm tra trước.

#### 3.2.3 `chart_coordinator.py` — được phép tồn tại, nhưng không được giữ sổ `action_id`

`async-ui-action-rule.md` §2 cho phép đúng hình này (`<name>/coordinators/<feature>_coordinator.py`,
Presenter sở hữu, tiêm qua constructor), nhưng kèm một cấm rõ ràng:

> *"**A Coordinator MUST NOT own independent FSM state or its own action-ownership/cancellation
> bookkeeping** […] That bookkeeping has exactly one owner — the Presenter […] never reimplemented
> per-Coordinator."*

Việc nạp nến + tính chỉ báo là tác vụ nền do người dùng khởi tạo (đổi symbol, đổi khung thời
gian), nên nó **có** `action_id`/chống callback cũ. Chủ sở hữu là `TradingPresenter`;
`chart_coordinator` làm việc rồi báo ngược lại qua Presenter. §2 cũng nói trước cái bẫy: *"Splitting
a Presenter into Coordinators that each keep their own action-id counter"* là cùng một lỗi
Single-Scope Cohesion với việc rải một FSM ra nhiều file.

#### 3.2.4 Thiếu `preview.py` — có guard test, sẽ đỏ ngay

`ui-presentation-rule.md`: *"Every UI package […] MUST maintain a `preview.py` declaring
`build_preview() -> QWidget`"*, khoá bằng
`tests/unit/presentation/ui/test_preview_fixtures_exist.py`. Guard đó quét **mọi** thư mục con của
`src/presentation/ui/screens/`, nên `trading/` không có `preview.py` sẽ làm gate đỏ ngay lần đầu
thêm màn. Cả 4 màn hiện có đều có file này.

Guard không chỉ kiểm tồn tại: nó **chạy** `build_preview()` ở chế độ offscreen và bắt cả lỗi cú
pháp/runtime của QML. Nên `preview.py` là việc phải làm cùng lúc với view, không phải dọn dẹp sau.

#### 3.2.5 Bố cục thư mục — MVP trio nằm **phẳng**, không có `view_models/`

`ui-presentation-rule.md`: *"keep `<name>_presenter.py`, `<name>_view.py`, `<name>_view_model.py`,
and QML files **flat** at the top level of the screen's folder. Group only helper modules into
`<name>/logic/` or `<name>/helpers/` when size warrants it."*

Đã kiểm cả 4 màn hiện có: **không** màn nào có thư mục `view_models/`. Thư mục con duy nhất đang
được dùng rộng rãi là `coordinators/` — đúng thứ `async-ui-action-rule.md` §2 cho phép riêng.

### 3.3 Review mockup A/B/C (2026-09-02) — 18 điểm, đối chiếu với model dữ liệu thật

Mock 3 trạng thái + dải banner. **Cái làm đúng, ghi trước vì nó là ràng buộc khó nhất:** tách
giá MAINNET / giá khớp TESTNET được xử lý ở **bốn** chỗ độc lập (badge cạnh tiêu đề chart, nhãn
`TRỤC GIÁ: MAINNET`, đường `GIÁ KHỚP TESTNET` kẻ ngang, và câu giải thích dưới chart nói rõ lệch
bao nhiêu USDT). Đúng yêu cầu §2.2b. Bốn hạn mức đều hiện. Trạng thái rỗng nói *"chưa có gì xảy
ra"* chứ không giống hỏng.

Dưới đây là cái thiếu, xếp theo mức chặn.

#### A. Thiếu control — mock ngầm giả định chúng tồn tại

| # | Thiếu | Bằng chứng |
| :-: | :--- | :--- |
| **1** | **Khối lượng vào lệnh (position sizing)** | **Nặng nhất.** Cấu hình đang ship **không đặt nổi một lệnh nào**. `_LIVE_SIZING = PERCENT_OF_EQUITY 20%`, `_LIVE_LEVERAGE = 1.0` hard-code trong `live_trading_coordinator.py:67-68`. Chạy thật với đúng số dư mock vẽ: `14 871.60 × 20% @ 64 105.35` → `0.046 BTC` = **2 948.85 USDT** > hạn mức **500** ⇒ **mọi lệnh bị chặn**. Mock vẽ `0.002 BTC` = 128.21 USDT ≈ **0.86%** vốn — không phải 20%. Tức mock đã giả định có control này |
| **2** | **Chọn chiến lược** *(user phát hiện)* | `trading.live_strategy_key` mặc định **rỗng** ⇒ `binance_bot_module.py:539` không dựng `StrategyEngine`, `MarketTickEventHandler` đứng im. 6 chiến lược đã đăng ký. Mock ghi `ema_cross(9,21)`; key thật là **`ema_crossover`** |
| **3** | **Tham số chiến lược** | Mock ghi `(9,21)`. Default thật trong `ema_crossover_strategy.py:16-17` là **12/26**. `fast_period`/`slow_period` là `input_int` — sửa được, nhưng không có chỗ nào để sửa |
| **4** | **Khung thời gian** | Header ghi `1m` nhưng **không có config key nào** cho interval, và `MarketTickEventHandler.handle()` **chỉ lọc `md.symbol`, không lọc `md.interval`**. Stream chạy đồng thời 1m và 5m cùng symbol ⇒ cả hai đổ vào **một** `StrategyEngine` ⇒ hỏng state chỉ báo — đúng nguy cơ docstring của chính class đó cảnh báo, nhưng nó chỉ cảnh báo cho *symbol* |

Bốn cái này cùng một gốc: `EPIC-021G` §6.7 đã ghi *"control UI thật thuộc `EPIC-021I`"*. Mock là
chỗ đáng ra phải trả món nợ đó.

#### B. Vẽ ô không có nguồn dữ liệu, hoặc nhãn sai nguồn

| # | Ô trong mock | Sự thật trong code |
| :-: | :--- | :--- |
| **5** | *"Số dư USDT **khả dụng** 14 871.60"* | `futures_account_reader.py:71` đọc **`walletBalance`**, không phải `availableBalance`. Hai số **khác nhau** ngay khi có margin — và trạng thái B vẫn hiện 14 871.60 *cùng lúc* với margin 128.20, tức nó đang là wallet, không phải khả dụng |
| **6** | *"Margin đang dùng"* | **Không có nguồn.** `ExchangeConnectionStatus` không có field này. Mock còn **tự mâu thuẫn**: rail ghi `128.20`, thẻ vị thế ngay dưới ghi `Margin 25.64` — `128.20` là **notional**, không phải margin |
| **7** | *"PnL chưa thực hiện"* ở rail | Không có field cấp tài khoản. Cộng từ `LivePosition.unrealized_pnl` được, nhưng phải gọi đúng tên là **tổng của các vị thế đang mở** |
| **8** | *"Mở lúc 14:35:02"* | `LivePosition` chỉ có `updated_at` = **lần đổi gần nhất**. `/fapi/v3/positionRisk` **không trả về thời điểm mở vị thế** |
| **9** | `THỜI GIAN` = `14:35:03.412881` | 6 chữ số = **microsecond**. Binance trả **millisecond**. Đây là dấu vết `datetime.now()` cục bộ — trái quyết định đã chốt ở §3.1 (dùng giờ của sàn) |
| **10** | Trạng thái C: số dư `12.40` | Rơi từ `14 871.60` xuống `12.40` mà margin chỉ 25.64 — không giải thích được. Câu *"Không đủ để đóng vị thế 128.21 USDT"* cũng sai cơ chế: lệnh đóng là `reduceOnly`, **không** cần thêm margin bằng notional |

#### C. Thiếu trạng thái

| # | Trạng thái | Vì sao bắt buộc |
| :-: | :--- | :--- |
| **11** | **Đang đối soát** + **từ chối bật** | §2.5 bắt buộc: bật → chạy reconciliation **trước** lệnh đầu; sàn có vị thế app không biết → **từ chối bật**. Toggle trong mock chỉ có 2 trạng thái. Theo `async-ui-action-rule.md` §2 đây là tác vụ nền do user khởi tạo ⇒ phải có kết cục nhìn thấy được |
| **12** | **Lệnh bị hạn mức chặn** | Cả hệ thống an toàn **không có hình nào**. CLI in `✘ CHẶN — one_position_per_symbol`; trên UI chỉ còn một dòng log trôi qua. Đây là thứ đang bảo vệ người dùng — nó xứng đáng một trạng thái hạng nhất |
| **13** | **Mất kết nối / chưa sẵn sàng** | Rào an toàn thứ **3** (`CONNECTION_NOT_READY`). Dải banner D có 3 trạng thái, không cái nào cho việc này |
| **14** | **Chưa cấu hình API key** | Sidebar có mục *"API & Credentials"*, không có trạng thái rỗng tương ứng ở màn này |
| **15** | **Lệnh bị sàn từ chối** | `binance_error_translator.py` đã dịch 5 mã (`-2019`, `-4164`, `-2022`, `-1003`, `-1013`). Chỉ trạng thái C có lỗi, và chỉ cho Dừng khẩn cấp |

#### D. Thiếu hành động — cơ chế đã có sẵn ở port

| # | Hành động | Đã có |
| :-: | :--- | :--- |
| **16** | **Huỷ 1 lệnh chờ** | `ITradingClient.cancel_order(symbol, client_order_id)` — bảng lệnh chờ không có nút nào |
| **17** | **Đóng 1 vị thế bằng tay** | Chỉ có Dừng khẩn cấp (tất-cả-hoặc-không). Người vận hành nhìn thấy một vị thế xấu **không làm gì được** ngoài giật cầu dao |
| **18** | **`PARTIALLY_FILLED`** | Cột `GIÁ TRẠNG THÁI` gộp giá + trạng thái. Trạng thái này cần **khớp/tổng**; footer B có ghi *"0 khớp một phần"* nên mock có biết, nhưng bảng chưa có chỗ hiển thị |

#### Hệ quả cho kế hoạch

Điểm **1** và **4** không phải góp ý thẩm mỹ — chúng là **defect trong code hiện tại**, lộ ra nhờ
mock:

- Sizing 20%/1x hard-code khiến bot **im lặng không đặt lệnh** trên mọi tài khoản có số dư
  > ~2 500 USDT. Không có log `INFO` nào nói "bị chặn vì notional", chỉ `result.blocked_by`.
- `MarketTickEventHandler` không lọc `interval` là lỗ hổng thật, độc lập với UI.

Prompt vòng 3 cho AI thiết kế, gom 4 control + 5 trạng thái + 6 chỗ sửa số liệu:
[`design/PROMPT_vong3_control_va_trang_thai_thieu.md`](../design/PROMPT_vong3_control_va_trang_thai_thieu.md).

Cả hai **đã mở hồ sơ riêng**, không lẫn vào task dựng màn:
[`BUG-084`](../../../bug_report/incomplete/BUG-084_live_sizing_hardcode_chan_moi_lenh.md) (sizing)
và [`BUG-085`](../../../bug_report/incomplete/BUG-085_live_tick_khong_loc_theo_interval.md)
(không lọc interval).

### 3.4 Review mock vòng 3 (2026-09-02) — 3/4 mục đạt, 1 mục chưa gửi

Đối chiếu trực tiếp với danh sách trong
[`PROMPT_vong3_control_va_trang_thai_thieu.md`](../design/PROMPT_vong3_control_va_trang_thai_thieu.md).

**§1 (4 control) — đạt cả 4.** Chiến lược, tham số (badge `2 ô` báo số lượng động), khung thời
gian, và sizing đều có mặt ở dải "CẤU HÌNH BOT". Vượt cả yêu cầu ở hai chỗ: notional/lệnh hiện
kèm `✓ dưới hạn mức 500` ngay tại chỗ cấu hình — đúng ràng buộc §1.1 *"phải thấy trước khi bật,
không phải sau tín hiệu đầu tiên"*; và câu hỏi thiết kế mở ở cuối §1 (đổi cấu hình được lúc đang
chạy không) đã có lập trường rõ: khoá `🔒` toàn dải khi giao dịch BẬT, mở lại khi TẮT — đúng
hướng an toàn hơn.

**§4 (6 chỗ sửa số liệu) — đạt cả 6**, đáng chú ý nhất là điểm cuối cùng: câu giải thích bịa lý
do *"không đủ để đóng vị thế 128.21 USDT"* đã được thay bằng *"Sàn trả mã -2019; app không suy
đoán nguyên nhân"* — đúng cách xử lý một lỗi sàn thật (`OrderRejectionReason`), không tự chế
thêm ý nghĩa. `walletBalance` đổi nhãn thành "Số dư ví", tách khỏi "margin"; giá trị vị thế
128.21 giờ nhất quán giữa rail và thẻ vị thế; timestamp còn 3 chữ số (mili-giây).

**§3 (3 hành động) — đạt cả 3.** Nút Huỷ trên từng lệnh chờ, nút Đóng trên từng vị thế, cột
`ĐÃ KHỚP` cho lệnh khớp một phần.

**§2 (5 trạng thái) — chưa có trong bản gửi.** Bốn khung nhận được (A/B/C/D) là đúng bốn khung
cũ, chỉ bổ sung control + sửa số liệu — không có khung nào cho: đang đối soát, từ chối bật, lệnh
bị hạn mức chặn, kết nối chưa sẵn sàng, chưa có API key.

**Quyết định: không mở vòng mock thứ 4 chỉ vì thiếu §2.** Theo `ONBOARDING.md` §7 — khi một
pattern đã có tiền lệ đã kiểm chứng ngay trong chính bộ mock này, dùng lại nó thay vì hỏi thêm.
Trạng thái C ("DỪNG KHẨN CẤP — THẤT BẠI MỘT PHẦN") đã tự vẽ đúng hình dạng cần cho 5 trạng thái
còn thiếu: một khối callout viền trái đậm màu, tiêu đề trạng thái, danh sách bước kèm ✓/✗, và
hành động khắc phục. Dải banner D cũng đã cho 3 mẫu banner phân biệt bằng ký hiệu + nhãn chữ,
không chỉ màu. Cả hai hình đó tổng quát hoá thẳng sang 5 trạng thái ở §2 mà không cần thiết kế
mới — việc còn lại là nội dung (14 lý do đã có tên trong code, không phải hình dạng mới), nên để
lại cho lúc code, không mở thêm vòng mock.

## 4. Kiểm thử

- **Unit (ViewModel):** 2 bảng render đúng từ dữ liệu `OrderFeed`; bảng rỗng khi chưa có gì (không
  phải crash, không phải hàng giả).
- **Unit (hợp đồng):** test `ast` hai chiều cho `ITradingView` — thành viên dùng mà chưa khai
  **và** khai mà không ai dùng đều đỏ, có khoá cả số đếm (`EPIC-013B`).
- **Unit:** bật công tắc khi reconciliation thấy vị thế lạ → công tắc **không** bật lên.
- **Integration:** `OrderFilledEvent` qua `OrderFeed` → dòng xuất hiện đúng ở bảng vị thế.
- **Sanity:** màn mới được tier quét tự động phát hiện; boot im lặng (`diagnostic_guard`), **0 test
  sanity mới được viết** — nếu phải viết thì test sanity cũ đã sai thiết kế.
- **Guard đã có sẵn, không phải viết mới — chỉ phải làm cho nó xanh:**
  `tests/unit/presentation/ui/test_preview_fixtures_exist.py` (mỗi màn có `preview.py`, và
  `build_preview()` chạy sạch ở offscreen, bắt cả lỗi QML — §3.2.4) và
  `tests/unit/presentation/ui/qml/test_qml_library_does_not_import_screens.py` (`EPIC-021L` —
  `qml/` không được import ngược `screens/`; liên quan trực tiếp tới lựa chọn A ở §3.2.2).

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
