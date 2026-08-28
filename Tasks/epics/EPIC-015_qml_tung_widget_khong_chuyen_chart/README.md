# EPIC-015 — QML từng widget, chart ở lại QtWidgets

**Trạng thái:** 📋 **Đề xuất — chưa bắt đầu.** Không có dòng code nào bị đổi.
**Ngày:** 2026-08-28
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

### 3.3 Theme không phải làm lại

`app_bootstrapper.py` **đang gọi** `get_theme_bridge(Palette.as_ui_dict())` trong production
hôm nay. Cầu `Palette` → QML còn sống nguyên. Một nguồn token, hai pipeline đọc.

---

## 4. Lộ trình — rủi ro tăng dần, mỗi bước rollback được

| Bậc | Việc | LOC view | Chart? | Vì sao ở đây |
| :--- | :--- | ---: | :---: | :--- |
| **0** | **Kit QML tối thiểu** ở `src/presentation/ui/qml/` — chỉ những shape 2 modal đầu cần | mới | — | `EPIC-006B` phải xong trước C/D/E vì cùng lý do: không có base thật thì mỗi màn tự chế style inline. **Chỉ xây cái bậc 1 cần**, không xây suy đoán. |
| **1** | **2 modal pilot** — `capital_dialog` + `timezone_picker_dialog` (nhỏ nhất, độc lập nhất) | ~200 | ❌ | Cửa sổ riêng ⇒ **zero rủi ro lồng nhau** (phép đo C). Lỗi lộ ngay. Rollback = trả lại 2 file. |
| **2** | **9 modal Backtest còn lại + 2 modal Data Management** | ~1.550 | ❌ | Cùng hình dạng bậc 1, lặp lại. Đây là chỗ QML trả lãi sớm nhất: modal toàn form + binding. |
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
