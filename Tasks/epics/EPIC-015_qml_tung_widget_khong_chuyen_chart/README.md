# EPIC-015 — QML từng widget, chart ở lại QtWidgets

**Trạng thái:** 🟡 **Đang làm** — bậc 0+1 xong 2026-08-28 (§4b); bậc 2's 3 component dùng
chung xong (§4c). **2026-08-29/30: 8 widget/kit mới xây đứng riêng** (chưa nối màn nào —
xem §4d) theo quyết định "tạo cái mới, còn cái cũ kệ nó". **Phase 1 (wiring vào màn thật)
ĐÃ XONG toàn bộ 2026-08-30** (§4e): `SymbolPicker` → Backtest; `TimeRangePicker` → Data
Management + Dev Board + Backtest (mở rộng phạm vi); `TimeframePicker` (modal, chọn-đóng
ngay) → Settings + Data Management + Backtest; `KlineInspectorTable` → Data Management.
`TimeframePickerOverlay` (widget cũ) **chưa xoá được** — `ChartToolbar` (Backtest + Dev
Board) vẫn dùng nó, đúng phần `TimeframeToolbar` thuộc Phase 4 (QML cạnh chart thật) chưa
làm. **Phase 2 ĐÃ XONG toàn bộ 2026-08-30:** `DatabaseStatusTable` → Data Management (phải
tự bổ sung thêm search + khoá nút khi busy vào chính component, không chỉ nối dây — màn cũ
đang có cả hai tính năng chạy thật, bỏ qua sẽ là hồi quy); `ProgressBanner` thay
`AppProgressBar` + nút Hủy riêng ở Data Management (lần đầu nhúng panel QML thẳng vào
layout màn hình, không qua `QmlOverlay`, an toàn vì màn này không có chart). Tiếp theo:
Phase 3 (`MetricsDetailPanel`, cần duyệt ngưỡng) → Phase 4 (cạnh chart, rủi ro cao nhất).
**Ngày:** 2026-08-28 (cập nhật 2026-08-30)
**Tiền đề:** [`ASSESSMENT_2026-08-28_qtwidgets_sang_qml.md`](../../reports/ASSESSMENT_2026-08-28_qtwidgets_sang_qml.md) §5 phương án **B**
**Yêu cầu user:**
> *"thế còn plan chuyển từ từ từng widget, không chuyển chart thì như nào?"*
> *"Widget sẽ tạo riêng ở 1 DIR, widget viewmodel sẽ được test riêng"*

---

## 1. Ràng buộc quyết định toàn bộ hình dạng

**QML lồng được vào trong QtWidgets. Chiều ngược lại thì không.**

Không có cách nào đặt một `QWidget` vào trong một `QQuickItem` — Qt không hỗ trợ.
`QQuickWidget` chỉ đi một chiều: nó *là* một `QWidget` chứa một scene QML.

Hệ quả, không thương lượng được:

- Chart là pyqtgraph (`QGraphicsView`) → **cái chứa chart phải là QtWidgets**.
- ⇒ Shell (`MainWindow` → `QStackedWidget`) **ở lại QtWidgets vĩnh viễn** trong epic này.
- ⇒ Màn **có chart** (Backtest, Dev Board): gốc view ở lại QtWidgets, **các panel con** thành
  `QQuickWidget` nằm cạnh chart.
- ⇒ Màn **không chart** (Settings, Data Management): cả route thành một `QQuickWidget`.
- ⇒ **Modal** thành QML **dễ nhất** — chúng là cửa sổ riêng, không lồng vào đâu cả.

Thứ tự thực hiện ở §4 **suy ra từ đúng ràng buộc này**, không phải sắp theo cảm tính.

## 2. Năm phép đo — chạy thật hôm nay, không suy đoán

Script ở `scratchpad/qmlspike/`. Kết quả:

| # | Câu hỏi | Kết quả |
| :--- | :--- | :--- |
| **A** | Panel QML ngồi **cạnh chart pyqtgraph** trong cùng một layout? | ✅ `Status.Ready`, cả hai `isVisible()`, chart `QRect(11,157,878,432)` dưới panel QML `QRect(11,11,878,140)` |
| **B** | `QQuickWidget` làm **cả một route** trong `QStackedWidget` của app? | ✅ Chuyển qua lại route QML ↔ route widget, cả hai `Ready` |
| **C** | Modal QML trong một `QDialog`? | ✅ `setModal(True)`, hiện, QML `Ready` |
| **D** | **pytest có với tới QML không?** | ✅ `root.findChild(QObject,"objName")`, `.property("text")`, và **`QTest.keyClicks` gõ thật xuyên QML vào ViewModel** |
| **E** | **Widget ViewModel test riêng, không GUI?** | ✅ `QApplication.instance()` là `None` suốt bài test; `Property`/`Signal`/`Slot`/lọc đều chạy |

**D và E là hai cái quan trọng nhất** — chúng phá rủi ro §3.2 của báo cáo đánh giá (mất 47 file
test). Không cần QtQuickTest, không cần runner thứ hai: `pytest` + `ci-local.ps1` hiện tại dùng
tiếp được.

> **Bẫy đã gặp trong lúc đo:** `QMetaObject.invokeMethod(field, "textEdited", Q_ARG(str, ...))`
> **fail** — `TextField.textEdited` của QtQuick Controls **không có tham số** (khác
> `QLineEdit.textEdited(str)` bên widget). Chữ ký signal QML ≠ widget. Đây đúng loại lỗi chỉ
> lộ lúc chạy mà §3.4 báo cáo cảnh báo. Cách né: `QTest.keyClicks` (kiểm chứng ở D) thay vì
> giả lập signal bằng tay.

## 3. Kiến trúc — theo đúng ràng buộc user đặt

### 3.1 Một DIR riêng cho widget

Soi gương quy ước `EPIC-001C` của Engine (`Sagittarius/UI/<Component>/`), nhưng ở phía app:

```
src/presentation/ui/qml/
  qmldir                          <- khai báo module, để .qml khác `import` được
  SymbolPicker/
    SymbolPicker.qml              <- shell khai báo, KHÔNG chứa logic
    symbol_picker_vm.py           <- ViewModel của widget, thuần Python
    NOTES.md                      <- vì sao widget này tồn tại (quy ước Engine)
  TimeframePicker/
  SymbolCard/
  ...
```

`.qml` và `_vm.py` **nằm cạnh nhau**, không tách hai cây — Single-Scope Cohesion
(`code-quality-rule.md` §7). Một widget là một thứ; tách shell và state ra hai thư mục xa nhau
là cách chúng trôi khỏi nhau.

### 3.2 Widget ViewModel giữ **toàn bộ** state và luật

Đây là điều làm kế hoạch này an toàn, và nó là ràng buộc user đặt ra:

| Tầng | Chứa gì | Test bằng gì |
| :--- | :--- | :--- |
| `<Component>.qml` | Chỉ bố cục, binding, animation | Smoke test qua `findChild` (ít, rẻ) |
| `<component>_vm.py` | **Toàn bộ** state, lọc, validate, luật hiển thị | **pytest thuần, không GUI** (phép đo E) |
| Screen ViewModel (`BaseQmlViewModel`) | Không đổi | Test hiện có, không đụng |
| Presenter / Coordinator | Không đổi | Test hiện có, không đụng |

Luật kèm theo, để tầng QML không phình ra: **không `if`/vòng lặp/tính toán trong `.qml`.**
Một biểu thức binding thì được; hai dòng JavaScript trở lên nghĩa là nó thuộc về VM.

Đối chiếu với hôm nay: `SymbolPickerOverlay` có `filtering.py` (thuần, 19 test) tách khỏi
widget rồi. **Đó chính là hình dạng cần** — `filtering.py` gần như thành `symbol_picker_vm.py`
nguyên vẹn.

### 3.3 Styling — quyết định user 2026-08-28

> *"styling nên remove luôn nhỉ, chưa cần style sớm"*

**Nhận, và nó làm bậc 0 nhỏ hẳn đi.** Không dựng kit QML, không thiết kế lại gì cả, không
đuổi theo pixel. Nhưng đo xong thì phải tách hai thứ đang bị gộp làm một:

| | |
| :--- | :--- |
| ✅ **Không thiết kế style sớm** | Đúng. Không kit, không component style, không token mới. |
| ❌ **Không có tầng style** | Không làm được, vì ba lý do đo được dưới đây. |

**Lý do 1 — "không style" không phải trung tính, nó là hộp trắng trên nền đen.** Đo thật:

```
Nền app (Palette.BG):                     #0a0a0c
Nút QtQuick Controls không style, ở giữa: #f5f5f5
```

Trong kế hoạch lai, modal QML mở **cạnh** màn QtWidgets đã style đầy đủ. Lệch này lộ ngay
lập tức, không phải "để sau tính".

**Lý do 2 — trên Windows, style áp sau sẽ im lặng không ăn.** Docstring của
`engine/runtime/qml_style.py` ghi rõ: style mặc định của Windows **bỏ qua không báo lỗi** mọi
override `background:`/`contentItem:`, chỉ log một dòng warning rồi vẽ chrome native. Bạn chạy
Windows. Hoãn styling = hoãn luôn việc phát hiện cái bẫy này tới đúng lúc tệ nhất.

**Lý do 3 — repo này đã dính đúng bệnh đó hai lần.** `EPIC-006B` bị đặt làm **điều kiện tiên
quyết** của C/D/E chính xác vì `EPIC-005` để lại *"8 widget đều tự viết `setStyleSheet` riêng —
đúng thứ đang gây lộn xộn"*. Bỏ tầng style không cho ra "không style", nó cho ra **N bản màu
inline riêng lẻ** phải gỡ sau.

**Cách làm giữ đúng ý bạn mà không dính ba cái trên — và nó gần như miễn phí, vì đã viết sẵn:**

| Việc | Chi phí |
| :--- | :--- |
| `ensure_qml_style()` — ghim style "Basic" cho customize được | 1 lệnh gọi, **code đã có ở Engine** |
| `register_theme(quick_widget)` — gắn `Theme` vào context | 1 lệnh gọi, **code đã có ở Engine** |
| Dùng token trần: `color: Theme.bgCard` | thay cho `color: "#151823"`, **không phải quyết định thiết kế** |

Cộng một luật từ bậc 0: **không hằng số màu trong `.qml`** — soi gương `guards.py` hiện đã cấm
hex literal ngoài `style.py`. Rẻ bây giờ, đắt về sau.

Tóm lại: **không có bậc "xây kit QML"**, đúng ý bạn. Chỉ hai lệnh gọi có sẵn và một luật.

### 3.4 Theme không phải làm lại

`app_bootstrapper.py` **đang gọi** `get_theme_bridge(Palette.as_ui_dict())` trong production
hôm nay. Cầu `Palette` → QML còn sống nguyên. Một nguồn token, hai pipeline đọc.

---

## 4. Lộ trình — rủi ro tăng dần, mỗi bước rollback được

| Bậc | Việc | LOC view | Chart? | Vì sao ở đây |
| :--- | :--- | ---: | :---: | :--- |
| **0** ✅ | **Chỉ hạ tầng, không kit** (§3.3): thư mục `src/presentation/ui/qml/`, một `QmlOverlay` host, luật cấm màu literal trong `.qml` | ~100 | — | Thu nhỏ theo quyết định styling của user. Không có component style nào được viết ở bậc này. |
| **1** ✅ | **2 modal pilot** — `capital_dialog` + `timezone_picker_dialog` (nhỏ nhất, độc lập nhất) | ~200 | ❌ | Cửa sổ riêng ⇒ **zero rủi ro lồng nhau** (phép đo C). Lỗi lộ ngay. Rollback = trả lại 2 file. |
| **2** ✅ | **Sửa lại sau phản biện của user (xem §4c): không phải "9 modal", là 3 component dùng chung + 5 modal Backtest ghép vào chúng.** Còn lại `time_range_picker` (ghép A+E, chưa làm) + `strategy_properties_dialog` (451 dòng, riêng — chính là dialog `BUG-064`, chưa làm) + 2 modal Data Management (bảng, chưa quyết) | ~700 | ❌ | Đếm lại theo **hình dạng**, không theo file — xem §4c. |
| **3** | **Settings** — cả route thành `QQuickWidget` | 443 | ❌ | Màn nhỏ nhất không chart (phép đo B). Pilot cho "cả route là QML". |
| **4** | **Data Management** — cả route | 2.452 | ❌ | Không chart, nhưng nặng bảng. Cân nhắc giữ `QListView` + model nếu QML `ListView` không bằng. |
| **5** | **Dev Board** — panel thành `QQuickWidget` cạnh chart | 1.399 | ✅ giữ | Lần đầu chạm pattern A (phép đo A). Màn có chart nhỏ hơn ⇒ làm trước Backtest. |
| **6** | **Backtest** — top panel + trade logs thành `QQuickWidget`; `backtest_view.py` (gốc, giữ chart) ở lại QtWidgets | 3.473 | ✅ giữ | Lớn nhất, nhận mockup nhiều nhất ⇒ lãi cao nhất, làm sau cùng khi pattern đã chắc. |
| **—** | **Chart** (`components/chart_card/`, 4.253 LOC, 26 file) | — | 🚫 | **Ngoài phạm vi vĩnh viễn trong epic này.** Xem báo cáo §3.1. |
| **—** | **Shell** (`main_window.py`, `QStackedWidget`, `Sidebar`) | — | 🚫 | Phải là QtWidgets để chứa chart (§1). |

**Tổng phải viết lại: ~9.500 LOC** — so với ~15.500 + chart của phương án "QML toàn bộ".
Chart 4.253 dòng **không bị đụng tới**.

Sau bậc 6, app ở trạng thái ổn định lâu dài: **shell + chart QtWidgets, mọi thứ khác QML.**
Đó không phải nửa đường — đó là đích.

## 4c. Bậc 2 — sửa lại sau phản biện của user

> *"92 Widget là do mình k reuse đó, chứ làm gì mà tới 92 loại"*

Đúng. Kế hoạch ban đầu liệt kê 11 modal còn lại như 11 việc, dù chính bậc 1's ghi chú đã nói
"cùng hình dạng, lặp lại". Đếm lại theo **hình dạng thật**, không theo tên file:

| Hình | Mô tả | Modal dùng | Đã có prototype? |
| :--- | :--- | :--- | :--- |
| **A. Chọn 1** | `Repeater`, click → emit → đóng | `timezone_picker` (bậc 1), `strategy_picker`, nửa preset của `time_range_picker` | ✅ |
| **B. Chỉ đọc** | Cùng `Repeater`/model, bỏ click | `limitations` | = A, cờ `selectable=False` |
| **C. Lưới thẻ chỉ đọc** | `Grid` 2 cột, không tương tác | `extended_metrics` | ❌ mới |
| **D. Checkbox multi-select** | Danh sách checkbox độc lập | `indicator_picker` (model sống), `order_execution` (cố định + khoá + loại trừ chéo) | ❌ mới |
| **E. Form validate** | `capital` (bậc 1) | nửa custom của `time_range_picker`, `strategy_properties` (451 dòng, riêng) | ✅ |
| **F. Bảng phân trang** | `QTableView`/`QListView` + model | `gap_inspector`, `kline_inspector` (Data Management) | chưa quyết — xem §3 gốc |

**9 modal Backtest thật ra có 4 hình, hai đã prototype ở bậc 1.** Xây 3 component dùng chung
(`SelectList` gộp A+B, `StatGrid` cho C, `CheckboxList` cho D) là đủ cho 5/9 modal ngay, không
phải viết 5 lần.

### Đã làm — 3 component + 5 modal

| Component | `.py` + `.qml` | Modal dùng nó |
| :--- | ---: | :--- |
| `SelectList` (thay `TimezonePicker` bậc 1, xoá không giữ forwarder) | 85 + 96 | `timezone_picker`, `strategy_picker`, `limitations` |
| `StatGrid` | 43 + 65 | `extended_metrics` |
| `CheckboxList` | 59 + 41 | `indicator_picker`, `order_execution` |

**389 dòng component, phục vụ 6 modal** (3 vừa port + `timezone_picker` port lại từ bậc 1).
Modal riêng (chỉ đấu dây, không còn logic UI) còn lại **~50–90 dòng mỗi cái** — xem
`strategy_picker_dialog.py`, `limitations_dialog.py` trong repo.

### Bốn phát hiện — hai cái đầu đã ghi ở §4b, hai cái mới lộ ra khi build 3 component:

**3. `Repeater` chỉ nhận đúng MỘT delegate.** `SelectList.qml` ban đầu đặt `Rectangle`
("selectItem_") và `Row` ("bulletItem_") làm **anh em trực tiếp** trong `Repeater`. Kết quả đo
được: `selectItem_` **không bao giờ được tạo** — chỉ delegate cuối cùng (`Row`) tồn tại, bất kể
`selectable` là gì. Không có lỗi biên dịch, không có warning — im lặng hoàn toàn. Sửa bằng cách
bọc cả hai vào một `Item` cha (một delegate thật cho mỗi index), cả hai `Rectangle`/`Row` thành
con của `Item` đó.

Đây đúng loại lỗi §3.4 của báo cáo đánh giá cảnh báo — nhưng còn kín hơn cả `findChild`/style vì
**không văng ra một dòng log nào**. Bắt được nhờ so `find_all_named(..., "selectItem_")` trả về
`0` thay vì `2` trong test tự viết.

**4. `Repeater { model: vm.rows }` phá huỷ và tạo lại TOÀN BỘ delegate mỗi lần rebuild.**
Đo bằng cách giữ tham chiếu Python của một `CheckBox` qua hai lần `rowsChanged.emit()` liên tiếp:
Python id đổi hoàn toàn giữa hai lần, item cũ trở thành vật đã chết. Binding vẫn đúng — **nhưng
chỉ khi tra cứu lại**. Hệ quả cho toàn bộ test: **không bao giờ giữ tham chiếu delegate qua một
lần refresh** — `_qml_test_support.find_named()`/`find_all_named()` phải được gọi lại sau mỗi
`rowsChanged`/`optionsChanged`/`cardsChanged`. Ghi một lần trong docstring của module đó thay vì
lặp lại ở từng test.

### Một helper dùng chung cho test

`tests/unit/presentation/ui/qml/_qml_test_support.py` — `named_descendants()`/`find_named()`/
`find_all_named()`, thay `findChild` (không với tới delegate của `Repeater`, phát hiện #1 của
bậc 1). Trước đây mỗi file test tự viết lại hàm này; gộp một chỗ sau khi thấy nó lặp lần thứ hai.

## 4b. Bậc 0 + bậc 1 — ĐÃ LÀM, và pilot tìm ra 3 thứ

**Trạng thái:** ✅ bậc 0 và bậc 1 xong 2026-08-28. Bậc 2 trở đi chưa bắt đầu.

Đã chuyển: `capital_dialog.py` (form có validate) và `timezone_picker_dialog.py` (danh sách).
Chọn cặp này vì chúng đo hai hình dạng khác nhau, không phải hai bản sao của một hình dạng.

### Chi phí thật, không ước lượng

| | Widget (trước) | QML + VM (sau) |
| :--- | ---: | ---: |
| `capital_dialog.py` | 92 | 88 + `capital_vm.py` 96 + `Capital.qml` 50 |
| `timezone_picker_dialog.py` | 66 | 60 + `timezone_picker_vm.py` 74 + `TimezonePicker.qml` 44 |
| Hạ tầng dùng chung (`qml/host.py`) | — | 108, **một lần cho mọi modal sau** |
| Test | 2 file chạm dialog | **16 test VM (0,6 giây, không GUI)** + 6 smoke + 3 guard |

**Số dòng tăng ~2x, nhưng đó không phải toàn bộ câu chuyện:** phần tăng nằm ở `_vm.py` — nơi
`mypy`, `ruff` và `pytest` **nhìn thấy được**, và test chạy trong 0,6 giây không cần
`QApplication`. Phần `.qml` chỉ còn bố cục.

Chứng minh cụ thể ở `Capital`: bản widget cần `textChanged` nối ra, `capitalValidationMessageChanged`
nối vào, và `_sync_validation()` giữ nhãn lỗi + nút Apply khớp nhau — **ba chỗ để lệch**. Bản QML:
`text: vm.text`, `visible: vm.validationMessage !== ""`, và `canApply` là property dẫn xuất.
**`BUG-064` không tái diễn được ở hình dạng này.**

### Ba phát hiện — đây là lý do pilot tồn tại

**1. `findChild` KHÔNG với tới delegate của `Repeater`.**
`findChild(QObject, "tzItem_UTC")` trả về `None` dù cả 6 delegate tồn tại và đúng tên. Item do
`Repeater` tạo nhận parent *thị giác* là parent của Repeater, **không phải** parent `QObject` —
nên đệ quy của `findChild` không thấy. Cách đúng: `column.childItems()` hoặc `repeater.itemAt(i)`.

`findChild` **vẫn đúng** cho item khai báo tĩnh (mọi lookup trong test `Capital` dùng nó). Ghi lại
ở helper `_rows_of()` trong `test_qml_modal_bodies.py`, một chỗ duy nhất.

Nếu không có pilot, cái này lộ ở bậc 2 khi đã viết xong 11 modal.

**2. Style mặc định phải ghim trước khi nạp QML đầu tiên.**
`ensure_qml_style()` phải chạy trong `QmlOverlay.__init__`, không chỉ ở bootstrapper — test dựng
dialog trực tiếp và không bao giờ chạy bootstrapper, nên nếu không có nó, test sẽ xanh trên
chrome native mà **người dùng không bao giờ thấy**.

**3. QML mang lại tiếng ồn stderr lúc teardown.**
Huỷ scene QML sinh ra `TypeError: Cannot read property ... of null` khi binding đánh giá lại trên
context đã chết. Đã thử `closeEvent` xoá source: **đo được là không đổi gì** (16 dòng cả hai
chiều, vì dialog bị GC chứ không bị close), nên đã **gỡ ra thay vì ship một comment nói sai**.

Đây đúng là thứ `CLAUDE.md` luật #2 sinh ra để cảnh báo — và tôi dính đúng nó trong lúc làm:
`| tail` cho ra một bức tường đỏ dưới một lần chạy **10/10 pass**. Với QML quay lại, luật
"`> logfile 2>&1` rồi grep, đừng `| tail`" **không còn là di sản** — nó lại đang có hiệu lực.

## 5. Cái được và cái phải trả

**Được:**
- Binding hai chiều miễn phí — `BUG-064` không tái diễn được ở màn đã chuyển.
- Dựng mockup nhanh, đúng lý do gốc `BOT-030` và vẫn đang là workflow chính (bạn gửi mock hôm nay).
- Chart không bị đụng ⇒ **né hoàn toàn rủi ro duy nhất giết được dự án**.
- Test **mạnh hơn hiện tại** ở màn đã chuyển: logic nằm trong VM thuần, chạy không cần Qt GUI,
  nhanh hơn và ít flaky hơn test widget (`tests/sanity` hiện đang có 1 ResourceWarning và một
  segfault ngẫu nhiên ở tier integration).

**Phải trả — nói thẳng, đây là chi phí thật và nó vĩnh viễn:**
- **Hai pipeline styling.** `apply_role`/`StyleRole` (widget, cho chart + shell) **và** style QML.
  Đây đúng là lý do `EPIC-006` bỏ QML: *"một stack, một cách styling, một cách test"*. Kế hoạch
  này **cố ý mua lại chi phí đó** để đổi lấy tốc độ mockup. Đó là đánh đổi, không phải bữa trưa
  miễn phí.
- **Lỗi QML chỉ lộ lúc render** — `mypy`/`ruff` không nhìn thấy `.qml`. Giảm nhẹ bằng §3.2 (logic
  nằm hết trong `.py` được gác), nhưng không triệt tiêu.
- Chữ ký signal QML ≠ widget (bẫy ở §2) — mọi test viết lại phải qua `QTest`, không giả lập tay.

## 6. Điều kiện dừng — chốt bây giờ, không chốt lúc đang đau

- **Bậc 1 (2 modal pilot) vượt 3 lần ước lượng → DỪNG**, đánh giá lại trước khi làm bậc 2.
  (Khuôn `EPIC-005`/`EPIC-006` đều dùng ngưỡng này.)
- Regression thị giác không sửa được trong buổi đó → rollback (nhánh riêng, chưa merge).
- Gate không giữ baseline chụp ngay trước mỗi bậc → dừng, sửa nguyên nhân, không merge lúc đỏ.
- **Số test mất (không port được) vượt 20 file → DỪNG.** Phép đo D/E nói con số này *nên* gần 0;
  nếu nó không gần 0 thì tiền đề §3.2 sai và phải biết ngay.
- Bậc 5 (Dev Board, lần đầu QML ngồi cạnh chart thật) có bất kỳ hiện tượng chart nhấp nháy /
  không vẽ / tụt FPS → **DỪNG, chốt phạm vi ở bậc 4.** Bậc 1–4 vẫn giữ được nguyên giá trị vì
  chúng không chạm màn có chart.

## 7. Việc phải làm trước bậc 0

`.agents/rules/qml-rule.md` đang mô tả thế giới **trước** `EPIC-006`: nó nói QML là mặc định,
và trỏ tới chart QtQuick "permanent, never in scope" — thứ nay đã bị xoá khỏi cây. Agent nào
đọc nó hôm nay cũng bị dẫn sai. Phải viết lại theo §1/§3 của epic này **trước** khi có dòng
`.qml` đầu tiên.

## 4d. 2026-08-29/30 — 8 widget/kit mới xây đứng riêng, chưa nối màn nào

Quyết định user 2026-08-29 lặp lại nhiều lần: *"tạo cái mới, còn cái cũ kệ nó"* — mỗi widget
dưới đây được xây xong (QML + VM + test riêng, `preview.py` để xem qua
`scripts/preview-qml.ps1`/`uml_preview.ps1`), nhưng **không widget nào nối vào composition
root của màn thật** tại thời điểm viết mục này. Widget cũ (QtWidgets) mỗi widget dưới đây định
thay thế **vẫn đang chạy y nguyên** trong production.

| Widget mới | Thay cho (QtWidgets) | Màn đích |
| :--- | :--- | :--- |
| `SymbolPicker` | `components/symbol_picker/overlay.py` | Backtest, Dev Board, Data Mgmt, Settings |
| `TimeframePicker` (+`TimeframeToolbar`) | `components/timeframe_picker/overlay.py`, `ChartToolbar` | Backtest, Dev Board, Settings |
| `TimeRangePicker` | `components/date_range_picker.py`/`DateRangeOverlay` | Data Mgmt, Dev Board |
| `TradeLogTable` | `backtest_trade_logs_panel.py` | Backtest |
| `MetricsDetailPanel` | `ExtendedMetricsDialog`/`StatGrid` (đang live) | Backtest — cần duyệt ngưỡng Sharpe/Sortino/Calmar tự chế trước khi wiring thật |
| `DatabaseStatusTable` | `_status_row.py` | Data Management |
| `KlineInspectorTable` | `kline_inspector_dialog.py` | Data Management |
| `kit/` (Button, DialogShell, LogPanel, PanelHeader, StatusPill, ProgressBanner, StatCard) | `StyledButton`, `Overlay`, `LogPanel`, `AppProgressBar`, `StatCard` cũ | Nhiều màn — 3 cái (`TimeframeToolbar`, `StatusPill`, `StatCard`/`ProgressBanner` ở Backtest) nằm cạnh chart thật, xem §4e |

Chi tiết per-widget (lý do thiết kế, cái gì mockup có mà pass này chưa xây) nằm ở `NOTES.md`
của chính thư mục widget đó (`src/presentation/ui/qml/<Widget>/NOTES.md`) — không chép lại ở
đây để tránh bản sao trôi.

## 4e. 2026-08-30 — Kế hoạch wiring 4-phase (đã duyệt) và tiến độ

Trước khi wiring bất kỳ widget nào ở §4d vào màn thật, design as-is/to-be được trình và duyệt
(`.agents/ONBOARDING.md` §12.5.3). Phát hiện chính: **8 widget/kit ở §4d không cùng một mức rủi
ro** — `qml-rule.md` §0 đã xếp "Panel QML cạnh chart" (bậc 5/6) khác hẳn "Modal QML" (bậc 1/2,
đã chứng minh 6 lần). Thứ tự đã duyệt:

- **Phase 1 (đang làm — rủi ro thấp nhất, toàn bộ là Modal QML độc lập cửa sổ riêng):**
  `SymbolPicker`, `TimeRangePicker`, `TimeframePicker` (chỉ phần modal lưới, không đụng
  `TimeframeToolbar`), `KlineInspectorTable`.
  - ✅ **`SymbolPicker` → Backtest xong (2026-08-30).** `SymbolPicker.qml` tự vẽ `Popup` riêng
    (không qua `QmlOverlay`) — theo đúng `qml-rule.md` §0.1, một `Popup` trong `QQuickWidget`
    không tự che được phần QtWidgets xung quanh, nên host mới là
    `SymbolPickerModal` (`qml/SymbolPicker/symbol_picker_modal_host.py`): một `QDialog` app-modal
    thật, không có chrome title/footer (vì `.qml` tự vẽ hết), bọc `QQuickWidget`. Adapter
    `BacktestSymbolPickerSource` (`backtest_modals/backtest_symbol_picker_source.py`) hiện thực
    `ISymbolPickerSource`, giải quyết lệch hợp đồng `SymbolPreferences.toggle_favourite()` (toggle)
    so với `set_favourite(symbol, value)` (set) bằng cách chỉ toggle khi trạng thái khác yêu cầu.
    `ensure_qml_style()` được tách ra `qml/style.py` dùng chung giữa `QmlOverlay` và host mới
    (hai host cùng cần một cái pin style, không viết lại — `qml-rule.md` §0.2). Test: 6 test
    tích hợp dựng `SymbolPickerModal`/`SymbolPickerDialogWidget` thật (không mock QML) +
    7 test thuần cho adapter (0 `QApplication`). Data Management và Dev Board's
    `SymbolPickerOverlay` **chưa đụng** — vẫn dùng bản QtWidgets cũ.
  - ✅ **`TimeRangePicker` → Data Management + Dev Board + Backtest xong (2026-08-30).**
    Phạm vi ban đầu (`NOTES.md` cũ) chỉ nêu Data Management + Dev Board; user mở rộng thêm
    Backtest sau khi được chỉ ra Backtest có `TimeRangePickerDialog` cùng hình (preset-list,
    không calendar) chưa ai nối vào component chung — xác nhận tương thích nhãn preset trước
    khi làm (7d/30d/90d/365d/all/custom khớp `TimeRangePickerVM`, cộng "Hôm nay" là bonus chấp
    nhận được). Host dùng chung `qml/TimeRangePicker/time_range_picker_dialog.py`
    (`TimeRangePickerDialog(QmlOverlay)`, callback-constructed, không nhận `ISource` Port vì
    `TimeRangePickerVM` không cần một cái — khác `SymbolPicker`) — cả ba màn constructor trực
    tiếp, không lặp lại chrome/footer/Apply-enable ba lần. Data Management wiring
    `selectedInterval` thật (`describe()` từ `components/timeframe_picker/catalogue.py`) qua
    `TimeRangeCardWidget.set_timeframe_source()`; Dev Board không có khái niệm timeframe nào lộ
    ra `DashboardQmlViewModel` nên dùng hằng số fallback 60s/"1m" có ghi chú (giống hành vi cũ
    của `pick_date_range()`, giờ đặt tên thay vì ẩn); Backtest có adapter thuần
    `BacktestTimeRangeSource` (`backtest_modals/backtest_time_range_source.py`) đọc range hiệu
    lực qua `resolve_time_range()` và ghi lại kết quả áp dụng thành preset `CUSTOM`. Xoá hẳn
    `components/date_range_picker.py`/`pick_date_range()` và test của nó — không còn nơi nào
    gọi sau khi cả ba màn chuyển (`kit/overlays/date_range_overlay.py`'s `DateRangeOverlay`/
    `RangePreset` giữ nguyên, là primitive dùng chung khác không phụ thuộc bridge này). Test:
    7 test thuần cho `BacktestTimeRangeSource` (0 `QApplication`) + 9 test QML thật (host chung
    + composition root Backtest) + test wiring cho Data Management/Dev Board — toàn bộ
    `tests/unit/` (2624 test) và `tests/sanity/` (24 test) xanh.
  - ✅ **`TimeframePicker` (modal) → Settings, Data Management, Backtest xong (2026-08-30).**
    Chọn-và-đóng ngay, không có Áp dụng — khớp đúng hành vi `TimeframePickerOverlay._choose()`
    cũ (`.qml`'s delegate gọi thẳng `vm.choose(code)`, không có bước Apply riêng), nên host mới
    (`qml/TimeframePicker/timeframe_picker_dialog.py`'s `TimeframePickerDialog(QmlOverlay)`)
    không override `_build_buttons()`. `TimeframeVM` cần thêm `get_pinned`/`set_pinned` (phục vụ
    `TimeframeToolbar` — Phase 4) mà cả 3 màn chưa có state lưu trữ nào cho — dùng tạm
    `PinnedTimeframes`, một set trong bộ nhớ **riêng từng màn, không lưu qua phiên**, ghi rõ đây
    là khoảng trống cần Phase 4 giải quyết bằng **một state dùng chung** giữa toolbar và picker
    (không phải 3 bản độc lập nữa). **`TimeframePickerOverlay` (widget cũ) không xoá được** —
    `ChartToolbar` (nút "…" trên header chart Backtest lẫn Dev Board) vẫn gọi nó, chính là phần
    `TimeframeToolbar` thuộc Phase 4 chưa làm tới. Test: 12 test host QML thật + wiring 3 màn.
  - ✅ **`KlineInspectorTable` → Data Management xong (2026-08-30).** Thay
    `KLineInspectorDialog` (348 dòng QtWidgets) bằng `KlineInspectorDialogWidget(QmlOverlay)`
    (~75 dòng) + adapter thuần `DataManagementKlineInspectorSource`. Không có nút footer nào —
    khớp đúng dialog cũ (chỉ đóng bằng nút × title bar/Escape, chưa từng override
    `_build_buttons()`). Đúng phạm vi đã chốt trong `NOTES.md`: bỏ pagination (virtualize bằng
    `ListView`), hoãn audit + jump-to-date, bỏ hẳn page-size selector. Xoá `_kline_row.py`/
    `_kline_columns.py` (chỉ dialog cũ dùng); `kline_inspector_table_model.py` (nguồn dữ liệu
    thật) giữ nguyên. Test: 5 test adapter thuần + 7 test QML thật + 4 test wiring màn.

  **Cả 4 mục Phase 1 đã xong** — toàn bộ `tests/unit/` (2647 test) và `tests/sanity/` (24 test)
  xanh sau khi gộp cả hai thay đổi trên, cộng guard `test_widget_guards_hold.py` (bare-Qt-base
  ratchet) không bị chạm vì mọi host mới đều kế thừa `QmlOverlay`.
- ✅ **Phase 2 — xong 2026-08-30.**
  - **`DatabaseStatusTable` → Data Management.** Nặng hơn các mục Phase 1 vì phải bổ sung
    thật vào chính component (không chỉ nối dây): màn cũ đang có ô tìm kiếm và khoá 4 nút
    hành động (KLines/Gaps/Sync/Clear) khi đang sync, cả hai chạy thật — `DatabaseStatusVM`
    trước đó chưa có (`NOTES.md` tự ghi "no search box, no wired row actions yet"). Đã thêm
    `DatabaseStatusFilterProxy` vào bên trong VM (`rowsModel` trả proxy, không phải model
    thô), `setSearchText`/`actionsEnabled` (Slot/Property), và ô tìm kiếm thật trong
    `.qml`. Host mới `DatabaseStatusPanel(kit.Panel)` — **lần đầu `QQuickWidget` nhúng thẳng
    lên `Panel` thay vì qua `QmlOverlay`**, vì bảng này nằm trong layout màn hình, không phải
    modal (`qml-rule.md` §0's hai hình "Modal QML" đều không áp dụng). Xoá
    `_status_row.py`/`_status_columns.py`/`row_delegate.py` (chỉ đường render cũ dùng).
  - **`ProgressBanner` → thay `AppProgressBar` + nút Hủy riêng, Data Management.** Host mới
    `ProgressBannerWidget(QQuickWidget)` — **lần đầu nhúng panel QML thẳng vào layout màn
    hình mà không qua bất kỳ chrome nào** (không `Overlay`, không `Panel`), vì
    `ProgressBanner.qml` tự vẽ mọi thứ kể cả nút Hủy. An toàn vì Data Management không có
    chart — không đụng bản dùng ở `backtest_top_panel.py` (cạnh chart thật, thuộc Phase 4).
    Phần trăm đọc thẳng `DataManagementViewModel.progressPercent` (đã thêm sẵn ở Phase 1,
    tự kẹp 0-100 và chống chia 0) — không tính lại lần hai.
  - Test: toàn bộ `tests/unit/` (2649 test), `tests/sanity/` (24 test), guard
    `test_widget_guards_hold.py` (5 test — `Panel`/`QQuickWidget` không phải bare Qt base nên
    không chạm ratchet), `tests/integration/.../test_database_user_flow.py` (4 test) đều xanh.
- **Phase 3 (cần user duyệt ngưỡng trước khi làm):** `MetricsDetailPanel` thay
  `ExtendedMetricsDialog` — cơ chế wiring an toàn, nhưng 3 ngưỡng verdict (Sharpe/Sortino/Calmar)
  là tự chế, cần user chốt trước khi vào màn đang live.
- **Phase 4 (rủi ro cao nhất — pattern "QML cạnh chart" chưa từng chạy trong production, dừng
  theo điều kiện ở §6 nếu chart giật/rớt khung hình):** `TimeframeToolbar`, `StatusPill`
  (Dev Board), `StatCard` + `ProgressBanner` ở Backtest top panel — cả bốn nằm cạnh chart thật.
