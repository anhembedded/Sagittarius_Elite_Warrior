---
name: QML Widget Rule
description: QML sống lại đúng một chỗ — widget riêng lẻ nhúng qua QQuickWidget, không phải shell hay chart. Kiến trúc 1 widget = 1 thư mục (.qml + _vm.py), khi nào bỏ qua ViewModel riêng, style token bắt buộc từ ngày đầu, và các gotcha Qt Quick đã đo được thật (Repeater 1 delegate, rebuild toàn bộ, findChild không với tới).
trigger: on_file_change
patterns:
  - "**/*.qml"
  - src/presentation/ui/qml/**/*.py
---

# 🎨 QML WIDGET STANDARDS

> **Lịch sử đảo chiều hai lần — đọc trước khi cho rằng bất kỳ dòng nào dưới đây là "mặc định
> toàn app":**
>
> 1. **`BOT-030` → `EPIC-005` (chọn QML làm mặc định).** Lý do duy nhất từng ghi thành văn:
>    *"AI dịch mockup sang code trực tiếp hơn ở QML."* Callout gốc 2026-08-23 giữ nguyên văn
>    ngay dưới đây, đánh dấu **ĐÃ HẾT HIỆU LỰC** — không xoá, để biết vì sao đảo lần 1.
> 2. **`EPIC-006` (2026-08-24, bỏ hẳn QML).** Quyết định user: *"triết lý hiện tại của dự án là
>    không dùng QML để giảm chi phí phát triển."* QtWidgets trở thành **mặc định cho toàn app**,
>    kể cả chart (`BUG-039` chứng minh tiền đề "chart phải ở QtQuick vì hiệu năng" sai — bản
>    QtQuick **chưa từng render một khung hình nào trong production suốt 5 ngày**).
> 3. **`EPIC-015` (2026-08-28, QML quay lại — đúng MỘT phạm vi hẹp).** User: *"chuyển từ từ từng
>    widget, không chuyển chart."* Đây là quy tắc hiện hành, thay thế cả hai giai đoạn trên.
>    Xem [`EPIC-015`](../../Tasks/epics/EPIC-015_qml_tung_widget_khong_chuyen_chart/README.md)
>    cho lộ trình/tiến độ; **file này chỉ giữ kiến trúc chuẩn — cách xây, không phải xây tới đâu.**

> #### ⚠️ SUPERSEDED — callout gốc 2026-08-23 (`EPIC-005A`'s ADR), giữ nguyên văn
>
> QML stays the **default** for any screen that receives new UI directly from a user-supplied
> mockup — `BOT-030`'s own reason for choosing QML (*"AI translates a mockup to code more
> directly in QML than QtWidgets"*) was re-checked against git history and found still true
> and still in active use (15+ mockup-driven tasks since `BOT-030`, most recently in
> `backtest`/`dashboard`).
>
> `EPIC-005` migrates a narrow, deliberately-chosen slice — form/lookup screens
> (`SettingsScreen`, parts of `DatabaseScreen`) — because those screens are not where new
> mockups keep arriving. This rule's QML standards still govern every screen that epic does
> not touch, including **the chart (`native/chart_renderer/`, permanent QtQuick, never in
> scope)** and `backtest`/`dashboard` (`EPIC-005F`, indefinitely deferred).
>
> **Cả ba khẳng định trên đều sai theo trạng thái hiện tại**, giữ lại đúng nguyên nhân
> `architecture-rule.md` §7.2 giữ lại luật đã đảo của nó: đọc lịch sử phải biết đã bị thay, không
> phải đoán. Sai cụ thể: (a) QML không còn là mặc định của bất kỳ màn nào — `EPIC-006`; (b)
> `native/chart_renderer/` đã bị xoá khỏi cây, và chart giờ **vĩnh viễn QtWidgets** vì ràng buộc
> lồng nhau (§0), không phải vì "permanent QtQuick"; (c) `backtest`/`dashboard` **đang** nhận
> QML trở lại theo `EPIC-015`, không còn "indefinitely deferred".

---

## 0. Ràng buộc gốc — quyết định mọi thứ khác trong file này

**QML lồng được vào QtWidgets. Chiều ngược lại Qt không hỗ trợ.** Chart là pyqtgraph
(`QGraphicsView`, thuần QtWidgets) — nên:

- **Shell** (`main_window.py`, `QStackedWidget`, `Sidebar`) — **QtWidgets vĩnh viễn**.
- **Chart** (`src/presentation/ui/components/chart_card/`, 4.253 dòng) — **QtWidgets vĩnh
  viễn**. Không phải vì hiệu năng (tiền đề đó đã sai — xem "Lịch sử đảo chiều" ở đầu file) mà vì ràng buộc
  lồng nhau: cái gì chứa chart thì phải là QtWidgets.
- **Mọi thứ khác** — widget riêng lẻ (modal, panel, picker, form field) **có thể** xây bằng QML,
  nhúng vào bên trong một chrome QtWidgets qua `QQuickWidget`. Đây không phải "QML là mặc
  định" (đã bị `EPIC-006` bác) cũng không phải "QtWidgets là mặc định" theo nghĩa cấm QML —
  đây là **quyết định theo từng widget**, dựa trên §2 dưới đây.

Ba pattern lồng nhau đã đo là chạy được thật (`EPIC-015` spike A/B/C):

| Pattern | Ai chứa ai | Ví dụ trong repo |
| :--- | :--- | :--- |
| Panel QML cạnh chart | `QVBoxLayout` (widget) chứa cả `QQuickWidget` lẫn `ChartCard` | chưa dùng — dành cho bậc 5/6 |
| Cả route là QML | `QStackedWidget` chứa một `QQuickWidget` làm cả màn | chưa dùng — dành cho Settings/Data Management |
| Modal QML | `QDialog`/`Overlay` chứa `QQuickWidget` làm phần thân | `QmlOverlay` (`src/presentation/ui/qml/host.py`) — **đã có, đang dùng** |

### 0.1 Modal QML — hai hình, không phải một

Hàng "Modal QML" ở trên chỉ đúng cho **một** tình huống. Có tình huống thứ hai, và nhầm giữa
hai cái này là cách một component tự dựng lại thứ Qt đã cho sẵn. Lý do kỹ thuật, đo được từ
chính Qt chứ không suy đoán: `Popup`/`Dialog` của `QtQuick.Controls` dim/chặn tương tác thông
qua một `Overlay.overlay` gắn theo **`Window`** chứa nó — một `QQuickWidget` là cửa sổ Qt Quick
riêng của chính nó, tách khỏi các widget QtWidgets đứng cạnh. Nên `Popup` mở bên trong một
`QQuickWidget` nhỏ **không thể** che phần QtWidgets xung quanh nó, dù code không hề báo lỗi.

| Host là gì | Cách đúng | Vì sao |
| :--- | :--- | :--- |
| Route/màn hình vẫn là QtWidgets (hiện tại: hầu hết màn) | `QmlOverlay` (`QDialog` QtWidgets thật, chứa thân QML) | Chỉ một `QDialog` thật mới dim/chặn được toàn bộ ứng dụng khi phần còn lại là QtWidgets. `.qml` bên trong **chỉ là layout thân** (`Column`/`Grid`/`ScrollView` — xem `SelectList`/`CheckboxList`/`StatGrid`/`Capital`), không tự dựng modal của chính nó. Đây là hình duy nhất 5 component hiện có dùng, và chúng đang đúng — không cần sửa gì.|
| Route/màn hình đã là toàn bộ QML (bậc 3+ của `EPIC-015`: Settings, Data Management sau khi chuyển) | `Popup`/`Dialog` gốc `QtQuick.Controls` làm root của component modal | Lúc này cả route là một `QQuickWindow` duy nhất, nên `Popup` dim đúng toàn màn. Dùng `Popup`/`Dialog` thay vì tự dựng `Item` + backdrop + bắt phím tay — chúng cho sẵn Escape-to-close, `closePolicy` (đóng khi click ra ngoài), và focus scope; tự viết lại là trùng lặp bề mặt Qt đã viết và test sẵn, thêm bề mặt lỗi phải tự bảo trì (đúng nghĩa "không common" — Popup/Dialog mới là idiom chuẩn của Qt Quick cho modal, không phải một `Item` tự quản `visible`). |

`SymbolPicker.qml` hiện rơi vào ô thứ hai (dùng độc lập, không qua `QmlOverlay` — xem
`NOTES.md` cùng thư mục) nhưng lại tự dựng `Item` + backdrop + bàn phím tay thay vì
`Popup`/`Dialog`. Chưa phải lỗi cấp bách — component này chưa nối vào màn hình thật nào, chỉ
`preview.py` và test dùng nó (xem việc còn treo ở §9) — nhưng khi viết lại, đổi root thành
`Popup`/`Dialog` là điểm sửa chính.

### 0.2 `src/presentation/ui/qml/` chính thức là nơi dựng QML component — không còn là khu thử nghiệm

Quyết định user 2026-08-29: thư mục này **chính thức**, không phải "vùng pilot của
`EPIC-015`" nữa. Hệ quả trực tiếp, áp dụng cho mọi lần thêm hoặc sửa bất cứ thứ gì ở đây:

- **Cái gì dùng chung được thì phải dựng dùng chung, không viết bản sao "gần giống".**
  Trước khi tạo `.qml` mới, tra bảng hình đã có ở §2 và các VM đã có (`SelectList`,
  `StatGrid`, `CheckboxList`, `TimeRangePicker`, ...). Một hình "gần giống nhưng hơi
  khác" là tín hiệu để **tổng quát hoá** component có sẵn (thêm cờ, thêm callback) —
  đúng cách `SelectListVM` đã hấp thụ `TimezonePickerVM` cũ, xoá bản gốc chứ không giữ
  lại làm forwarder (xem docstring `select_list_vm.py`) — không phải tín hiệu để viết
  một widget mới song song.
- **Thêm tính năng vào một widget đã có luôn phải tự hỏi trước: design hiện tại còn
  đúng, hay tính năng này sắp bị vá vào một chỗ không hợp?** Nếu không hợp, sửa design
  — đổi hợp đồng VM, đổi cách interface chia read/write, tách lại component — **không
  hotfix, không giữ nguyên design cũ rồi thêm nhánh đặc biệt (`if is_special_case:`)
  cho vừa tính năng mới.** Ví dụ đã xảy ra thật: `ISymbolPickerSource` chỉ có `get_*`
  (read-only) cho tới khi `toggleFavourite()` cần ghi lại — thay vì để VM tự ghi tắt
  qua signal rồi coi là xong, hợp đồng được sửa thêm `set_favourite()` để đối xứng
  đọc/ghi (xem lịch sử ở `ISymbolPickerSource`'s docstring).
- **Ưu tiên áp dụng design pattern đã có trong chính file này** — Port/interface tường
  minh (`architecture-rule.md`, cấm duck-typing ngầm), VM callback-constructed dùng
  chung (§1.1), VM giữ toàn bộ state và luật (§1.2), đúng hình modal theo host (§0.1)
  — hơn là nghĩ ra cách làm riêng cho từng widget.

---

## 1. Kiến trúc: 1 widget QML = 1 thư mục

```
src/presentation/ui/qml/
  host.py                    QmlOverlay — chrome QtWidgets, thân QML
  <Widget>/
    <Widget>.qml             chỉ bố cục + binding, KHÔNG logic
    <widget>_vm.py            toàn bộ state + luật, KHÔNG import QML
    NOTES.md                  vì sao widget này tồn tại, ai dùng nó
```

`.qml` và `_vm.py` **nằm cạnh nhau trong cùng thư mục** — Single-Scope Cohesion
(`code-quality-rule.md` §4): một widget là một thứ, tách shell và state ra hai chỗ xa nhau là
cách chúng trôi khỏi nhau. Ví dụ đang chạy thật: `SelectList/`, `CheckboxList/`, `StatGrid/`,
`Capital/`.

### 1.1 ViewModel widget: ai tạo, ai giữ

**Python (màn cha) tạo ViewModel, tiêm vào `.qml` qua context property `vm`.** `.qml` **không
bao giờ** tự khởi tạo backend của chính nó (không `id: backend` gọi constructor Python bên
trong file `.qml`) — giữ đúng luật §5.1 "QML thuần khai báo" đã có từ trước, và giữ việc khởi
tạo/inject nằm ở composition root (màn hình), nơi có thể test bằng mock/callback mà không cần
dựng QML.

```python
# Trong dialog/panel Python — composition root
self._widget_vm = SelectListVM(
    get_options=lambda: view_model.strategyOptions,   # đọc sống từ VM màn hình
    get_current=lambda: view_model.selectedStrategyKey,
)
super().__init__(..., qml_file=_QML, context={"vm": self._widget_vm})
```

```qml
// .qml — chỉ đọc, không tính toán
Text { text: vm.rows[0].label }
```

### 1.2 ViewModel widget giữ TOÀN BỘ state và luật

| Tầng | Chứa gì | Test bằng gì |
| :--- | :--- | :--- |
| `<Widget>.qml` | Chỉ bố cục, binding, animation | Render smoke test (ít, rẻ) |
| `<widget>_vm.py` | Lọc, tính `selected`, validate, format | **pytest thuần, `QApplication.instance()` là `None` suốt bài test** |

Đo được thật: 16 test `SelectListVM`/`CheckboxListVM`/`StatGridVM` chạy **0,6 giây, không
`QApplication`, không QML**. Luật cứng: **không `if`/vòng lặp/tính toán trong `.qml`.** Một
biểu thức binding thì được (`visible: modelData.subtitle !== ""`); hai dòng JavaScript trở lên
nghĩa là nó thuộc về `_vm.py`.

### 1.3 Khi nào **KHÔNG** cần ViewModel widget riêng

> User chốt 2026-08-28: *"các UI mà viewmodel không có đóng góp gì thêm, chỉ chuyển đổi 1:1 thì
> không cần viewmodel."*

Đây **không phải luật mới, độc lập** — nó là áp dụng cụ thể của `architecture-rule.md` §7.2 vào
đúng trường hợp này: *"Abstraction ở đây không có nghĩa đẻ thêm lớp trung gian cho có."* Một
ViewModel widget mà toàn thân chỉ là `return self._screen_vm.x` không phải hợp đồng — nó là một
bản sao thứ hai của state đã có sẵn, và bản sao là đúng hình dạng lỗi `BUG-064` từng gây ra: hai
chỗ giữ cùng một sự thật, không có gì buộc chúng khớp nhau.

**Cách quyết định — hỏi đúng thứ tự:**

1. **Widget có dùng chung cho ≥1 màn hình khác nhau không** (như `SelectList`/`CheckboxList`/
   `StatGrid` — Backtest dùng, sau này Data Management cũng dùng được)? → **Luôn có VM riêng**,
   dựng bằng callback (`get_options`, `get_rows`, ...), bất kể một lần gọi cụ thể trông có
   "1:1" hay không. Lý do: cái hợp đồng ("đưa cho tôi list đúng hình `{id, label, ...}`") **là**
   giá trị — nó tách widget khỏi hình dạng ViewModel của bất kỳ màn nào, giữ nó test được và
   dùng lại được. `StatGridVM` chỉ uppercase title + map `Tone` → tên chuỗi — trông "nhỏ", vẫn
   giữ, vì nó phục vụ đúng vai trò đó.
2. **Widget chỉ dành cho đúng một màn** (không định dùng lại)? Hỏi tiếp: `.qml` có cần **giá
   trị dẫn xuất** không có sẵn trên ViewModel màn đó không (`selected` tính từ so sánh, `canApply`
   tính từ trạng thái validate, format lại chuỗi, gộp nhiều property thành một)?
   - **Có** → có VM riêng. Đây chính là `CapitalVM`: `canApply` là dẫn xuất, không phải copy.
   - **Không, chỉ đọc/ghi thẳng property đã có, không biến đổi gì** → **bỏ VM riêng**, tiêm
     thẳng ViewModel màn hình vào context property: `context={"vm": view_model}`. `.qml` bind
     thẳng `vm.someScreenProperty`.
3. Widget có cần **giấu bớt** bề mặt ViewModel màn hình (màn có 40 property không liên quan,
   phơi hết ra là rò rỉ đóng gói) không? → có VM riêng, dù không biến đổi gì, để giới hạn API.

Không có widget nào trong `EPIC-015` hiện tại vi phạm chiều ngược (tất cả đều qua được bài kiểm
tra #1 hoặc #2) — nghĩa là chưa cần dọn gì, quy tắc này áp dụng **từ giờ về sau**.

### 1.4 "Widget" ở đây không phải quy ước riêng của repo — nó là `Component` của Qt

Tài liệu chính thức: [`QML Component type`](https://doc.qt.io/qt-6/qml-qtqml-component.html).

Mỗi file `.qml` **tên viết hoa chữ cái đầu** (`SelectList.qml`, `CheckboxList.qml`, `Capital.qml`)
tự động là một **Component type** của Qt — engine coi cả file đó là định nghĩa một kiểu UI dùng
lại được, có thể `import` và khởi tạo nhiều lần. §1's "1 widget = 1 `.qml`" không phải một phát
minh riêng của app — nó là chọn xếp mỗi Component sẵn có của Qt vào một thư mục riêng cùng
`_vm.py`/`NOTES.md` của nó (§1 ở trên), chứ không định nghĩa lại khái niệm.

Qt cũng có dạng khai báo **inline**, `Component { ... }`, dùng khi việc khởi tạo phải **trễ/lazy**
thay vì ngay lập tức — hai chỗ dùng chuẩn là delegate của `ListView`/`Repeater` và
`sourceComponent` của `Loader`. Đây chính là khái niệm đứng sau hai chỗ đã có trong file này:
gotcha §4.2 (`Repeater` phá huỷ và tạo lại toàn bộ delegate — vì mỗi delegate *là* một Component
được instantiate lại) và khuyến nghị "`Loader` để dựng theo yêu cầu" ở §6.6. Ghi tên khái niệm ra
đây để không ai phải tra lại Qt docs mới nhận ra hai chỗ đó cùng một gốc.

**Một bẫy đặt tên liên quan** (theo tài liệu Qt, không phải đo trong repo này — xem ghi chú đầu
§4 về ranh giới "đo được" so với suy đoán): tên file `.qml` viết **thường** chữ đầu không được Qt
đăng ký thành type — nó vẫn load được bằng đường dẫn trực tiếp, nhưng không dùng lại được như một
Component qua `import`. Mọi `.qml` trong `src/presentation/ui/qml/<Widget>/` đã viết hoa đúng
(`SelectList.qml`, không phải `selectList.qml`) — giữ nguyên quy ước đó khi thêm widget mới.

---

## 2. Khi nào chọn QML cho một widget mới

QML không còn là mặc định của cả màn hình (đã bị `EPIC-006` bác, xem "Lịch sử đảo chiều" ở đầu
file). Chọn QML cho
**một widget cụ thể** khi:

- Nó khớp một trong các hình đã có component dùng chung (bảng dưới) — dùng lại, không viết
  `.qml` mới.
- Nó là phần của màn đang được `EPIC-015` di chuyển theo lộ trình (xem file epic).
- Nó nhận mockup ảnh trực tiếp và tốc độ dịch mockup → code đáng giá hơn chi phí hai pipeline
  style (lý do gốc `BOT-030`, vẫn đúng — xem báo cáo đánh giá
  [`ASSESSMENT_2026-08-28_qtwidgets_sang_qml.md`](../../Tasks/reports/ASSESSMENT_2026-08-28_qtwidgets_sang_qml.md)).

**Component dùng chung đã có — kiểm tra trước khi viết `.qml` mới:**

| Hình | Component | Dùng khi |
| :--- | :--- | :--- |
| Chọn 1 trong danh sách | `SelectList` | `Repeater`, click → emit → đóng |
| Danh sách chỉ đọc | `SelectList` (`selectable=False`) | cùng model, bỏ click |
| Lưới thẻ chỉ đọc | `StatGrid` | không tương tác, chỉ hiển thị số |
| Checkbox multi-select | `CheckboxList` | độc lập từng dòng, luật khoá/loại trừ (nếu có) nằm ở dialog, không ở VM |
| Form có validate | tự viết theo mẫu `Capital` | field + kết quả validate cần đồng bộ |

---

## 3. Style — bắt buộc từ ngày đầu, kể cả khi "chưa cần thiết kế"

> User 2026-08-28: *"styling nên remove luôn nhỉ, chưa cần style sớm."* Đúng cho phần **thiết
> kế** (không kit, không token mới, không đuổi pixel). **Sai nếu áp dụng cho việc dùng token —
> đó không phải styling, đó là baseline đúng.**

Lý do đo được, không suy đoán:

1. **"Không style" là hộp trắng trên nền đen**, không phải trung tính. Đo thật: nút QtQuick
   Controls mặc định `#f5f5f5` trên nền app `#0a0a0c`.
2. **Style native của Windows bỏ qua `background:` mà không báo lỗi** — chỉ log warning rồi vẽ
   chrome mặc định. Hoãn styling nghĩa là hoãn phát hiện bẫy này tới đúng lúc tệ nhất (máy user).
3. Repo này đã dính đúng bệnh "mỗi widget tự vẽ" hai lần (`EPIC-005` để lại 8 `setStyleSheet`
   riêng lẻ; `EPIC-006B` phải làm điều kiện tiên quyết chính vì thế).

**Bắt buộc cho mọi `.qml` mới, không có ngoại lệ "để sau":**

- Gọi `ensure_qml_style()` (ghim style `"Basic"`) — làm trong `QmlOverlay.__init__`/host dùng
  chung, **không chỉ ở app bootstrap**: test dựng dialog trực tiếp, không qua bootstrapper, nếu
  chỉ ghim ở bootstrap thì test xanh trên chrome native mà người dùng không bao giờ thấy.
- Mọi màu **phải** là `Theme.<token>` (`register_theme()` gắn context property `Theme`). **Cấm
  hex literal (`"#..."`) và tên màu literal (trừ `"transparent"`) trong `.qml`** — guard đã có,
  xem `test_qml_style_discipline.py`; soi gương guard hex-literal phía widget (`kit/guards.py`).
- Kiểm token tồn tại thật trước khi dùng, đừng đoán tên — `Tone.POSITIVE` map sang
  `Theme.success`, không phải `Theme.positive` (đo bằng `Palette.as_ui_dict()` trước khi ship,
  không suy ra từ tên biến Python).

Việc **thiết kế** (spacing scale, animation, elevation) vẫn hoãn được thoải mái — đó đúng là ý
user. Việc **dùng đúng token thay vì literal** thì không hoãn, vì chi phí sửa sau đắt hơn viết
đúng ngay từ đầu (một `sed` cho cả app so với dò từng file).

---

## 4. Qt Quick gotcha — đo được thật, không suy đoán

Bốn cái này **không lộ ra bằng lỗi biên dịch hay warning** — `ruff`/`mypy` không đọc `.qml`, và
Qt Quick tự nó im lặng khi bạn dùng sai. Đây là loại lỗi chỉ-lộ-lúc-chạy mà `qml-rule.md` bản cũ
(pre-`EPIC-006`) chưa từng gặp phải vì lúc đó `.qml` không có test tự động sâu tới mức này.

### 4.1 `Repeater` chỉ nhận đúng MỘT delegate

Đặt hai `Item` (ví dụ `Rectangle` cho hình chọn được + `Row` cho hình chỉ đọc) làm **anh em trực
tiếp** bên trong `Repeater` → chỉ cái cuối cùng được tạo, cái kia **không bao giờ instantiate**,
không lỗi, không warning. Sửa: bọc cả hai vào **một `Item` cha** cho mỗi index, cả hai làm con
của `Item` đó.

### 4.2 `Repeater { model: <list các dict/QVariantList> }` phá huỷ và tạo lại TOÀN BỘ delegate mỗi lần model đổi

Kể cả khi chỉ một phần tử thay đổi. Đo bằng cách giữ tham chiếu Python của một delegate qua hai
lần `rowsChanged.emit()` liên tiếp — id đổi hoàn toàn, item cũ là vật đã chết. **Không bao giờ
giữ tham chiếu delegate qua một lần refresh** — tra cứu lại sau mỗi
`rowsChanged`/`optionsChanged`/`cardsChanged`. Đây cũng là lý do hiệu năng cho luật model-view ở
§6.6: một list tĩnh nhỏ dùng `Repeater` được, một list lớn/cập nhật liên tục thì bọc
`QAbstractListModel` (Python) — nó phát `dataChanged` theo từng dòng thay vì rebuild cả khối.

### 4.3 `findChild` KHÔNG với tới item do `Repeater` tạo

Đã có helper đúng từ trước `EPIC-015` — `tests/conftest.py`'s `qml_item`/`find_qml_item` (đi
bằng `childItems()`, ghi chú gốc: *"verified empirically while building the QML sidebar"*, tức
là phát hiện này **đã có từ thời Sidebar QML**, không phải mới). **Dùng fixture đó**, đừng viết
lại. *(Nợ kỹ thuật đã dọn 2026-08-30: `EPIC-015` từng tự viết
`tests/unit/presentation/ui/qml/_qml_test_support.py` làm y hệt việc này vì không tìm trước.
File đó đã bị xoá — `find_qml_item` là tên canonical duy nhất, và `find_all_named` (prefix match
cho hàng của `Repeater`) giờ sống cùng nó trong `tests/conftest.py`; mọi call site đã chuyển
sang import từ đó. Xem việc còn treo cuối file, mục đã đánh dấu DONE.)* `findChild` vẫn đúng cho
item khai báo tĩnh, và cho ranh giới `Popup` (tách khỏi `childItems()` theo chiều ngược lại) —
không đổi phần đó.

### 4.4 Chữ ký signal QtQuick Controls khác widget tương đương

`TextField.textEdited` **không có tham số**; `QLineEdit.textEdited(str)` (widget) thì có. Giả
lập signal bằng tay (`QMetaObject.invokeMethod` với sai số tham số) fail **im lặng** hoặc báo
lỗi khó hiểu. Dùng `QTest.keyClicks`/`QTest.mouseClick` để mô phỏng hành động thật thay vì đoán
chữ ký signal.

---

## 5. 🧩 Code Practices trong `.qml`

### 5.1 Strict Separation of UI and Business Logic
- **QML is Purely Declarative View**: QML files must only define visual layout, theme bindings, micro-animations, and user interaction signals.
- **No Complex Inline JavaScript**: Move all calculations, data transformations, domain validation, and state machines into the widget's `_vm.py` (§1) or the screen's `Presenter`/`ViewModel`/`Domain`. Small view-local helpers (focus handling, invoking a slot, resetting an already-rendered input) are permitted only when they do not duplicate a business rule or become a second source of state.
- **One-Way Command Dispatch**: UI triggers actions by invoking `vm` slots/methods. The Presenter/coordinator handles the business logic and updates ViewModel properties.

### 5.2 Reactive Property Bindings (Over Manual Assignment)
- **Automatic Reactivity**: Always bind QML element properties directly to `vm` properties or `Theme`. Never break bindings with imperative assignments inside signal handlers.

### 5.3 Component Modularization & Single Responsibility (SRP)
- **Break Down God Components**: Treat 300 lines as a mandatory review threshold, not a blind line-count failure.
  - Shared widget shapes (current, `EPIC-015`): `SelectList.qml`, `CheckboxList.qml`, `StatGrid.qml`.
  - Screen-specific bodies: one `.qml` per `QmlOverlay` consumer (`Capital.qml`, ...).
- **Component File Structure**: shared widgets live in `src/presentation/ui/qml/<Widget>/` (§1); a `.qml` used by exactly one screen's one dialog stays there too — do not create a screen-local `.qml` folder elsewhere.

### 5.4 Consistent Naming Conventions
- **Unique Testable IDs**: Every interactive element MUST declare a stable `objectName` — it is the only thing `qml_item()`/`find_qml_item()` can search on. Never use a generated index as the only test identity.
- **Property & Signal Naming**: Properties `camelCase` (`isConfigDirty`); signals `camelCase` verb phrases (`runRequested`, `chosen`, `toggled`).

---

## 6. 🎨 Design Practices & Visual Excellence

### 6.1 Design System & Theme Consistency
See §3 above — this is now a hard gate, not a style preference.

### 6.2 Dynamic Responsive UI Sizing (No Rigid Fixed Geometry)
- **Zero Fixed Dimensions on Containers**: Never hardcode rigid pixel `width`/`height` on modals, dialogs, popups, or cards.
- **Layout Managers**: Use Qt Quick Layouts / `Column`/`Row` with `Layout.fillWidth`/`fillHeight` where applicable.
- **Clipped Scrolling**: Interior scrollable containers declare `ScrollView { clip: true }`.

### 6.3 Synchronized Table Column Proportions
For any data table/header grid built in QML, column widths MUST be declared centrally and both header and row delegates bind to the same definition.

### 6.4 Micro-Animations for Feedback & Polish
Subtle, non-blocking transitions (150–250ms) are welcome once a widget is functionally correct — never before. Do not add decorative animation to render-sensitive surfaces (this rule never applies to the chart, which stays QtWidgets regardless — §0).

### 6.5 Security & UI Injection Defense
Always declare `textFormat: Text.PlainText` on `Text` items rendering dynamic or external data (trade logs, error messages, symbol names, raw exception text).

### 6.6 High-Performance Model-View Patterns
A repeated, dynamic collection that can exceed 20 items, update incrementally, or be virtualized MUST be backed by a Python `QAbstractListModel` (e.g. `TradeLogModel`, `IndicatorScriptListModel`, `LogModel`) — it emits `dataChanged` per row instead of the wholesale rebuild §4.2 measures for a `Repeater`-over-list-of-dicts model. A small static list or a one-shot form (`SelectList`/`CheckboxList`/`StatGrid`'s own rows) may use a plain `QVariantList` property only when it is not transforming domain data at scale. Keep `Repeater` delegates lean; instantiate detail sections on-demand via `Loader` or collapsible panels.

---

## 7. 🧪 QML Quality Assurance & Testing

- **Sanity Verification**: Every `.qml` file must construct cleanly — no syntax errors, unbound property warnings, or null pointer errors. `QmlOverlay` (`src/presentation/ui/qml/host.py`) already turns a failed load into a raised `RuntimeError` instead of silently rendering a blank box — every widget host must do the same, not render-and-hope.
- **Widget VM tests need no GUI** (§1.2) — the majority of a widget's test coverage should live here, not in a rendered test.
- **Render tests are thin, on purpose**: only prove the `.qml` loaded and its bindings point at properties the VM actually has — the render-time class of error `mypy`/`ruff` cannot see. Do not duplicate VM-level logic assertions in a render test.
- **Reaching into a rendered scene**: use `qml_item(root, "objectName")` (`tests/conftest.py`) for `Repeater` delegates and ordinary visual descendants — see §4.3 for why `findChild` fails there. Qt `Popup` items are the one exception, detached from `childItems()` the other direction — use `overlay_root.findChild(object, "objectName")` for those. Never weaken either kind of test into a Presenter/private-property assertion merely because the item is inconvenient to find.
- **Never hold a delegate reference across a refresh** (§4.2) — re-look-up after every `rowsChanged`/`optionsChanged`/`cardsChanged`.
- **Simulate real input, not a guessed signal signature** (§4.4) — `QTest.keyClicks`/`QTest.mouseClick` over hand-invoking a signal.

---

## 8. 🔍 UI Preview Convention & Live Tooling (BOT-031)

Unchanged by `EPIC-015` — still QtWidgets-first per screen, still enforced:

- **Mandatory `preview.py` per UI Package**: Every screen package in `src/presentation/ui/screens/<screen>/` and reusable component (`src/presentation/ui/components/sidebar/`) MUST have a `preview.py` exposing `build_preview() -> QWidget`.
- **Preview CLI Runner**: `.\scripts\preview-qml.ps1 <screen_name>` / `--list`. The script name is a historical misnomer (pre-`EPIC-006`) — it now previews QtWidgets screens too, name kept for the same reason a stale filename anywhere else in this repo is kept: renaming costs a diff for zero behaviour change.
- **Automated Guard Tests**: `tests/unit/presentation/ui/test_preview_fixtures_exist.py`.

---

## 9. Việc còn treo — ghi lại để không quên, không phải để làm ngay

- ~~`tests/unit/presentation/ui/qml/_qml_test_support.py` (`EPIC-015`) duplicates
  `tests/conftest.py`'s `qml_item`/`find_qml_item` almost exactly — written without searching
  for existing infra first. Needs consolidating onto the one canonical helper; not done here
  because this pass is rule-only (user: "ko code").~~ **DONE (2026-08-30).** File deleted.
  `find_qml_item` is the one canonical name (kept — it also backs the `qml_item` fixture's many
  existing callers); `find_all_named` (prefix match for a `Repeater`'s rows) moved into
  `tests/conftest.py` alongside it. `named_descendants` had no direct consumer that needed
  "named only, no prefix" — every real call site was already prefix-filtering, so it was fully
  absorbed into `find_all_named` rather than getting a second name in `conftest.py`. All 11
  consumer files now import both from `tests/conftest.py`.
- `QmlOverlay.root_object`'s docstring ("for tests to `findChild` into") is incomplete post-§4.3
  finding — true for statically-declared items, not for `Repeater` delegates. Small doc fix,
  same "not this pass" reason.
- `SymbolPicker.qml` hand-rolls its own backdrop/modal-card/keyboard handling on a plain `Item`
  instead of `Popup`/`Dialog` from `QtQuick.Controls` (§0.1) — not yet fixed because the
  component has no production host to verify against (only `preview.py` and its tests use it).
  User decision 2026-08-29: write the rule, do not touch the component in this pass — it will be
  rebuilt against this rule later.
