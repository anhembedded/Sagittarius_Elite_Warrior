---
name: QML Widget Rule
description: QML sống lại đúng một chỗ — widget riêng lẻ nhúng qua QQuickWidget, không phải shell hay chart. Kiến trúc 1 widget = 1 thư mục (.qml + _vm.py), khi nào bỏ qua ViewModel riêng, style token bắt buộc từ ngày đầu, và các gotcha Qt Quick đã đo được thật (Repeater 1 delegate, rebuild toàn bộ, findChild không với tới).
trigger: on_file_change
patterns:
  - "**/*.qml"
  - src/presentation/ui/qml/**/*.py
---

# 🎨 QML WIDGET STANDARDS

File này chỉ giữ **kiến trúc chuẩn — cách xây, không phải xây tới đâu**; lộ trình/tiến độ ở
[`EPIC-015`](../../Tasks/epics/EPIC-015_qml_tung_widget_khong_chuyen_chart/README.md).

## 0. Ràng buộc gốc — quyết định mọi thứ khác trong file này

**QML lồng được vào QtWidgets. Chiều ngược lại Qt không hỗ trợ.** Chart là pyqtgraph
(`QGraphicsView`, thuần QtWidgets) — nên:

- **Shell** (`main_window.py`, `QStackedWidget`, `Sidebar`) — **QtWidgets vĩnh viễn**.
- **Chart** (`src/presentation/ui/components/chart_card/`) — **QtWidgets vĩnh viễn**, vì ràng
  buộc lồng nhau: cái gì chứa chart thì phải là QtWidgets (không phải vì hiệu năng).
- **Mọi thứ khác** — widget riêng lẻ (modal, panel, picker, form field) **có thể** xây bằng QML,
  nhúng vào trong một chrome QtWidgets qua `QQuickWidget`.

QtWidgets là mặc định toàn app; QML **opt-in theo từng widget**, quyết định theo §2. Ba pattern
lồng nhau đã đo là chạy được thật (`EPIC-015` spike A/B/C):

| Pattern | Ai chứa ai | Ví dụ trong repo |
| :--- | :--- | :--- |
| Panel QML cạnh chart | `QVBoxLayout` (widget) chứa cả `QQuickWidget` lẫn `ChartCard` | chưa dùng |
| Cả route là QML | `QStackedWidget` chứa một `QQuickWidget` làm cả màn | chưa dùng — Settings/Data Management |
| Modal QML | `QDialog`/`Overlay` chứa `QQuickWidget` làm phần thân | `QmlOverlay` (`src/presentation/ui/qml/host.py`) — đang dùng |

### 0.1 Modal QML — hai hình, không phải một

Lý do kỹ thuật (đo từ chính Qt): `Popup`/`Dialog` của `QtQuick.Controls` dim/chặn tương tác qua
`Overlay.overlay` gắn theo **`Window`** chứa nó, mà một `QQuickWidget` là cửa sổ Qt Quick riêng
tách khỏi các widget QtWidgets đứng cạnh — nên `Popup` mở trong một `QQuickWidget` nhỏ **không thể**
che phần QtWidgets xung quanh, mà không hề báo lỗi.

| Host là gì | Cách đúng | Vì sao |
| :--- | :--- | :--- |
| Route/màn hình vẫn là QtWidgets (hầu hết màn hiện nay) | `QmlOverlay` (`QDialog` QtWidgets thật, chứa thân QML) | Chỉ một `QDialog` thật mới dim/chặn được toàn app khi phần còn lại là QtWidgets. `.qml` bên trong **chỉ là layout thân** (`Column`/`Grid`/`ScrollView` — xem `SelectList`/`CheckboxList`/`StatGrid`/`Capital`), không tự dựng modal của chính nó. |
| Route/màn hình đã là toàn bộ QML | `Popup`/`Dialog` gốc `QtQuick.Controls` làm root của component modal | Cả route là một `QQuickWindow` duy nhất nên `Popup` dim đúng toàn màn. Dùng `Popup`/`Dialog` thay vì tự dựng `Item` + backdrop + bắt phím tay — chúng cho sẵn Escape-to-close, `closePolicy`, focus scope; tự viết lại là trùng lặp bề mặt Qt đã test sẵn. |

`SymbolPicker.qml` rơi vào ô thứ hai nhưng tự dựng `Item` + backdrop + bàn phím tay — §9.

### 0.2 `src/presentation/ui/qml/` là nơi chính thức dựng QML component

- **Dùng chung được thì phải dựng dùng chung, không viết bản sao "gần giống".** Trước khi tạo
  `.qml` mới, tra bảng hình ở §2 và các VM đã có (`SelectList`, `StatGrid`, `CheckboxList`,
  `TimeRangePicker`, ...). Hình "gần giống nhưng hơi khác" là tín hiệu **tổng quát hoá** component
  có sẵn (thêm cờ, thêm callback) — như `SelectListVM` hấp thụ `TimezonePickerVM`, xoá bản gốc chứ
  không giữ làm forwarder — không phải tín hiệu viết widget mới song song.
- **Thêm tính năng vào widget đã có: hỏi trước design hiện tại còn đúng không.** Nếu không hợp,
  sửa design (đổi hợp đồng VM, đổi cách interface chia read/write, tách lại component) — **không
  hotfix, không giữ design cũ rồi thêm nhánh `if is_special_case:`**. Ví dụ: `ISymbolPickerSource`
  chỉ có `get_*` cho tới khi `toggleFavourite()` cần ghi; hợp đồng được thêm `set_favourite()` để
  đối xứng đọc/ghi.
- **Ưu tiên design pattern đã có trong file này** — Port/interface tường minh
  (`architecture-rule.md`, cấm duck-typing ngầm), VM callback-constructed (§1.1), VM giữ toàn bộ
  state và luật (§1.2), đúng hình modal theo host (§0.1) — hơn là cách riêng cho từng widget.

## 1. Kiến trúc: 1 widget QML = 1 thư mục

```
src/presentation/ui/qml/
  host.py                  QmlOverlay — chrome QtWidgets, thân QML
  <Widget>/
    <Widget>.qml           chỉ bố cục + binding, KHÔNG logic
    <widget>_vm.py         toàn bộ state + luật, KHÔNG import QML
    NOTES.md               vì sao widget này tồn tại, ai dùng nó
```

`.qml` và `_vm.py` **nằm cạnh nhau cùng thư mục** — Single-Scope Cohesion (`code-quality-rule.md`
§4): tách shell và state ra hai chỗ xa nhau là cách chúng trôi khỏi nhau. Ví dụ đang chạy:
`SelectList/`, `CheckboxList/`, `StatGrid/`, `Capital/`.

### 1.1 ViewModel widget: ai tạo, ai giữ

**Python (màn cha) tạo ViewModel, tiêm vào `.qml` qua context property `vm`.** `.qml` **không bao
giờ** tự khởi tạo backend của chính nó (§5.1) — khởi tạo/inject nằm ở composition root, nơi test
được bằng mock/callback mà không cần dựng QML.

```python
# dialog/panel Python — composition root; callback đọc sống từ VM màn hình
self._widget_vm = SelectListVM(get_options=lambda: view_model.strategyOptions,
                               get_current=lambda: view_model.selectedStrategyKey)
super().__init__(..., qml_file=_QML, context={"vm": self._widget_vm})
# .qml chỉ đọc, không tính toán:   Text { text: vm.rows[0].label }
```

### 1.2 ViewModel widget giữ TOÀN BỘ state và luật

| Tầng | Chứa gì | Test bằng gì |
| :--- | :--- | :--- |
| `<Widget>.qml` | Chỉ bố cục, binding, animation | Render smoke test (ít, rẻ) |
| `<widget>_vm.py` | Lọc, tính `selected`, validate, format | **pytest thuần, `QApplication.instance()` là `None` suốt bài test** |

Đo được thật: 16 test `SelectListVM`/`CheckboxListVM`/`StatGridVM` chạy **0,6 giây, không
`QApplication`, không QML**. Luật cứng: **không `if`/vòng lặp/tính toán trong `.qml`** — một biểu
thức binding thì được (`visible: modelData.subtitle !== ""`), hai dòng JavaScript trở lên là thuộc
về `_vm.py`.

### 1.3 Khi nào **KHÔNG** cần ViewModel widget riêng

> User chốt 2026-08-28: *"các UI mà viewmodel không có đóng góp gì thêm, chỉ chuyển đổi 1:1 thì
> không cần viewmodel."*

Áp dụng của `architecture-rule.md` §7.2 (*"Abstraction không có nghĩa đẻ thêm lớp trung gian cho
có"*): VM widget toàn thân chỉ `return self._screen_vm.x` không phải hợp đồng — nó là bản sao thứ
hai của state đã có, đúng hình dạng lỗi `BUG-064`: hai chỗ giữ cùng một sự thật, không gì buộc
chúng khớp nhau. **Hỏi đúng thứ tự:**

1. **Dùng chung cho ≥1 màn khác nhau?** (`SelectList`/`CheckboxList`/`StatGrid`) → **luôn có VM
   riêng**, dựng bằng callback (`get_options`, `get_rows`, ...), bất kể một lần gọi cụ thể trông
   "1:1" hay không: cái hợp đồng ("đưa list đúng hình `{id, label, ...}`") **là** giá trị — nó tách
   widget khỏi ViewModel của mọi màn. `StatGridVM` chỉ uppercase title + map `Tone` → chuỗi, vẫn giữ.
2. **Chỉ cho đúng một màn?** `.qml` có cần **giá trị dẫn xuất** không có sẵn trên ViewModel màn đó
   (`selected` tính từ so sánh, `canApply` tính từ validate, format chuỗi, gộp property)?
   **Có** → có VM riêng (`CapitalVM`: `canApply` là dẫn xuất, không phải copy). **Không, chỉ
   đọc/ghi thẳng property đã có** → **bỏ VM riêng**, tiêm thẳng ViewModel màn hình
   (`context={"vm": view_model}`), `.qml` bind thẳng `vm.someScreenProperty`.
3. Cần **giấu bớt** bề mặt ViewModel màn hình (màn 40 property không liên quan, phơi hết là rò rỉ
   đóng gói)? → có VM riêng dù không biến đổi gì, để giới hạn API.

Không widget nào hiện tại vi phạm — quy tắc áp dụng **từ giờ về sau**.

### 1.4 "Widget" ở đây là `Component` của Qt

[`QML Component type`](https://doc.qt.io/qt-6/qml-qtqml-component.html): file `.qml` **tên viết hoa
chữ cái đầu** tự động là Component type dùng lại được qua `import`; tên viết **thường** không được
Qt đăng ký thành type (load bằng đường dẫn trực tiếp thì được, `import` thì không) — **giữ quy ước
viết hoa**. Dạng inline `Component { ... }` là khởi tạo trễ/lazy (delegate `Repeater`/`ListView`,
`sourceComponent` của `Loader`) — gốc chung của §4.2 và khuyến nghị `Loader` ở §6.6.

## 2. Khi nào chọn QML cho một widget mới

QML không phải mặc định của cả màn hình. Chọn QML cho **một widget cụ thể** khi: nó khớp một hình
đã có component dùng chung (bảng dưới — dùng lại, không viết `.qml` mới); nó thuộc màn đang được
`EPIC-015` di chuyển; hoặc nó nhận mockup ảnh trực tiếp và tốc độ dịch mockup → code đáng giá hơn
chi phí hai pipeline style (lý do gốc `BOT-030`, vẫn đúng — xem
[`ASSESSMENT_2026-08-28_qtwidgets_sang_qml.md`](../../Tasks/reports/ASSESSMENT_2026-08-28_qtwidgets_sang_qml.md)).

**Component dùng chung đã có — kiểm tra trước khi viết `.qml` mới:**

| Hình | Component | Dùng khi |
| :--- | :--- | :--- |
| Chọn 1 trong danh sách | `SelectList` | `Repeater`, click → emit → đóng |
| Danh sách chỉ đọc | `SelectList` (`selectable=False`) | cùng model, bỏ click |
| Lưới thẻ chỉ đọc | `StatGrid` | không tương tác, chỉ hiển thị số |
| Checkbox multi-select | `CheckboxList` | độc lập từng dòng, luật khoá/loại trừ (nếu có) nằm ở dialog, không ở VM |
| Form có validate | tự viết theo mẫu `Capital` | field + kết quả validate cần đồng bộ |

## 3. Style — bắt buộc từ ngày đầu, kể cả khi "chưa cần thiết kế"

> User 2026-08-28: *"styling nên remove luôn nhỉ, chưa cần style sớm."* Đúng cho phần **thiết kế**
> (không kit, không token mới, không đuổi pixel). **Sai nếu áp dụng cho việc dùng token — đó không
> phải styling, đó là baseline đúng.**

Lý do đo được: (1) **"không style" là hộp trắng trên nền đen** — nút QtQuick Controls mặc định
`#f5f5f5` trên nền app `#0a0a0c`; (2) **style native của Windows bỏ qua `background:` mà không báo
lỗi**, chỉ log warning rồi vẽ chrome mặc định, nên hoãn styling là hoãn phát hiện bẫy tới lúc tệ
nhất (máy user); (3) repo đã dính bệnh "mỗi widget tự vẽ" hai lần (`EPIC-005` để lại 8
`setStyleSheet` riêng lẻ; `EPIC-006B` phải dọn). **Bắt buộc cho mọi `.qml` mới, không "để sau":**

- Gọi `ensure_qml_style()` (ghim style `"Basic"`) trong `QmlOverlay.__init__`/host dùng chung,
  **không chỉ ở app bootstrap**: test dựng dialog trực tiếp không qua bootstrapper, nếu chỉ ghim ở
  bootstrap thì test xanh trên chrome native mà người dùng không bao giờ thấy.
- Mọi màu **phải** là `Theme.<token>` (`register_theme()` gắn context property `Theme`). **Cấm hex
  literal (`"#..."`) và tên màu literal (trừ `"transparent"`) trong `.qml`** — guard đã có, xem
  `test_qml_style_discipline.py`; soi gương guard hex-literal phía widget (`kit/guards.py`).
- Kiểm token tồn tại thật trước khi dùng, đừng đoán tên — `Tone.POSITIVE` map sang `Theme.success`,
  không phải `Theme.positive` (đo bằng `Palette.as_ui_dict()` trước khi ship).

Việc **thiết kế** (spacing scale, animation, elevation) vẫn hoãn được; việc **dùng token thay vì
literal** thì không, vì sửa sau đắt hơn (một `sed` cho cả app so với dò từng file).

## 4. Qt Quick gotcha — đo được thật, không suy đoán

Bốn cái này **không lộ ra bằng lỗi biên dịch hay warning** — `ruff`/`mypy` không đọc `.qml`, Qt
Quick im lặng khi bạn dùng sai.

### 4.1 `Repeater` chỉ nhận đúng MỘT delegate

Đặt hai `Item` (ví dụ `Rectangle` cho hình chọn được + `Row` cho hình chỉ đọc) làm **anh em trực
tiếp** trong `Repeater` → chỉ cái cuối cùng được tạo, cái kia **không bao giờ instantiate**, không
lỗi, không warning. Sửa: bọc cả hai vào **một `Item` cha** cho mỗi index.

### 4.2 `Repeater { model: <list dict/QVariantList> }` phá huỷ và tạo lại TOÀN BỘ delegate mỗi lần model đổi

Kể cả khi chỉ một phần tử đổi. Đo bằng cách giữ tham chiếu Python của một delegate qua hai lần
`rowsChanged.emit()` liên tiếp — id đổi hoàn toàn, item cũ là vật đã chết. **Không bao giờ giữ
tham chiếu delegate qua một lần refresh**; tra cứu lại sau mỗi
`rowsChanged`/`optionsChanged`/`cardsChanged`. Đây cũng là lý do hiệu năng của luật model-view §6.6:
list tĩnh nhỏ dùng `Repeater` được, list lớn/cập nhật liên tục thì bọc `QAbstractListModel` (Python)
— nó phát `dataChanged` theo từng dòng thay vì rebuild cả khối.

### 4.3 `findChild` KHÔNG với tới item do `Repeater` tạo

Dùng `qml_item`/`find_qml_item` trong `tests/conftest.py` (đi bằng `childItems()`; ghi chú gốc:
*"verified empirically while building the QML sidebar"*), đừng viết lại — `find_qml_item` là tên
canonical duy nhất, `find_all_named` (prefix match cho hàng của `Repeater`) sống cùng nó ở đó.
`findChild` vẫn đúng cho item khai báo tĩnh và cho ranh giới `Popup` (tách khỏi `childItems()`
theo chiều ngược lại).

### 4.4 Chữ ký signal QtQuick Controls khác widget tương đương

`TextField.textEdited` **không có tham số**; `QLineEdit.textEdited(str)` (widget) thì có. Giả lập
signal bằng tay (`QMetaObject.invokeMethod` với sai số tham số) fail **im lặng** hoặc báo lỗi khó
hiểu. Dùng `QTest.keyClicks`/`QTest.mouseClick` để mô phỏng hành động thật thay vì đoán chữ ký.

## 5. 🧩 Code Practices trong `.qml`

- **5.1 Strict separation of UI and business logic.** QML files define only visual layout, theme bindings, micro-animations, and user-interaction signals. Move all calculations, data transformations, domain validation, and state machines into the widget's `_vm.py` (§1) or the screen's `Presenter`/`ViewModel`/`Domain`; small view-local helpers (focus handling, invoking a slot, resetting an already-rendered input) are permitted only when they do not duplicate a business rule or become a second source of state. UI triggers actions by invoking `vm` slots/methods — one-way command dispatch; the Presenter/coordinator runs the logic and updates ViewModel properties.
- **5.2 Reactive bindings over manual assignment.** Always bind QML element properties directly to `vm` properties or `Theme`. Never break bindings with imperative assignments inside signal handlers.
- **5.3 Component modularization & SRP.** Treat **300 lines** as a mandatory review threshold (not a blind line-count failure) for breaking up a god component: shared widget shapes (`SelectList.qml`, `CheckboxList.qml`, `StatGrid.qml`) vs. screen-specific bodies (one `.qml` per `QmlOverlay` consumer, `Capital.qml`, ...). Shared widgets live in `src/presentation/ui/qml/<Widget>/` (§1); a `.qml` used by exactly one screen's one dialog stays there too — do not create a screen-local `.qml` folder elsewhere.
- **5.4 Naming.** Every interactive element MUST declare a stable `objectName` — the only thing `qml_item()`/`find_qml_item()` can search on; never use a generated index as the only test identity. Properties `camelCase` (`isConfigDirty`); signals `camelCase` verb phrases (`runRequested`, `chosen`, `toggled`).

## 6. 🎨 Design Practices & Visual Excellence

- **6.1 Design system & theme consistency.** See §3 — a hard gate, not a style preference.
- **6.2 Responsive sizing, no rigid fixed geometry.** Never hardcode rigid pixel `width`/`height` on modals, dialogs, popups, or cards. Use Qt Quick Layouts / `Column`/`Row` with `Layout.fillWidth`/`fillHeight` where applicable. Interior scrollable containers declare `ScrollView { clip: true }`.
- **6.3 Synchronized table column proportions.** For any data table/header grid built in QML, column widths MUST be declared centrally and both header and row delegates bind to the same definition.
- **6.4 Micro-animations.** Subtle, non-blocking transitions (**150–250ms**) are welcome once a widget is functionally correct — never before. Do not add decorative animation to render-sensitive surfaces (never applies to the chart, which stays QtWidgets regardless — §0).
- **6.5 Security & UI injection defense.** Always declare `textFormat: Text.PlainText` on `Text` items rendering dynamic or external data (trade logs, error messages, symbol names, raw exception text).
- **6.6 High-performance model-view.** A repeated, dynamic collection that can exceed 20 items, update incrementally, or be virtualized MUST be backed by a Python `QAbstractListModel` (`TradeLogModel`, `IndicatorScriptListModel`, `LogModel`) — it emits `dataChanged` per row instead of the wholesale rebuild §4.2 measures for a `Repeater`-over-list-of-dicts model. A small static list or one-shot form (`SelectList`/`CheckboxList`/`StatGrid`'s own rows) may use a plain `QVariantList` property only when it is not transforming domain data at scale. Keep `Repeater` delegates lean; instantiate detail sections on-demand via `Loader` or collapsible panels.

## 7. 🧪 QML Quality Assurance & Testing

- **Sanity verification**: every `.qml` must construct cleanly — no syntax errors, unbound property warnings, null pointer errors. `QmlOverlay` (`src/presentation/ui/qml/host.py`) turns a failed load into a raised `RuntimeError` instead of silently rendering a blank box; every widget host must do the same, not render-and-hope.
- **Widget VM tests need no GUI** (§1.2) — the majority of a widget's coverage lives there, not in a rendered test.
- **Render tests are thin, on purpose**: only prove the `.qml` loaded and its bindings point at properties the VM actually has — the render-time class of error `mypy`/`ruff` cannot see. Do not duplicate VM-level logic assertions in a render test.
- **Reaching into a rendered scene**: use `qml_item(root, "objectName")` (`tests/conftest.py`) for `Repeater` delegates and ordinary visual descendants (§4.3). Qt `Popup` items are the one exception, detached from `childItems()` the other direction — use `overlay_root.findChild(object, "objectName")`. Never weaken either kind of test into a Presenter/private-property assertion merely because the item is inconvenient to find.
- **Never hold a delegate reference across a refresh** (§4.2) — re-look-up after every `rowsChanged`/`optionsChanged`/`cardsChanged`.
- **Simulate real input, not a guessed signal signature** (§4.4) — `QTest.keyClicks`/`QTest.mouseClick` over hand-invoking a signal.

## 8. 🔍 UI Preview Convention & Live Tooling (BOT-031)

- Every screen package in `src/presentation/ui/screens/<screen>/` and reusable component (`src/presentation/ui/components/sidebar/`) MUST have a `preview.py` exposing `build_preview() -> QWidget`.
- Run: `.\scripts\preview-qml.ps1 <screen_name>` / `--list` — it previews QtWidgets screens too, despite the name.
- Guard test: `tests/unit/presentation/ui/test_preview_fixtures_exist.py`.

## 9. Việc còn treo

Chưa có nơi tracking riêng cho hai việc này; giữ ở đây tới khi vào một task/epic thật:

- `QmlOverlay.root_object`'s docstring ("for tests to `findChild` into") chỉ đúng cho item tĩnh,
  không đúng cho delegate của `Repeater` (§4.3) — sửa doc nhỏ.
- `SymbolPicker.qml` tự dựng backdrop/modal-card/keyboard trên `Item` thay vì `Popup`/`Dialog`
  (§0.1) — chưa sửa vì chưa có host production để kiểm chứng; sẽ dựng lại theo luật này sau.
