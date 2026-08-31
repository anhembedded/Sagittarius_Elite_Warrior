# BUG-071 — CheckboxList/StatGrid QML quăng TypeError vì root item không có `parent`

**Reported date:** 2026-08-31
**Severity:** 🟡 **P3**
**Status:** ✅ Fixed 2026-08-31 (root-caused / reproduced / regression-tested / verified)

---

## 1. Hiện tượng (Symptom)

Log live user gửi (mở `OrderExecutionDialog` trong Backtest — "THỰC THI TẬP LỆNH"), ngay sau khi bật `HISTORICAL_TICK`:

```text
file:///.../src/presentation/ui/qml/CheckboxList/CheckboxList.qml:10:5: TypeError: Cannot read property 'width' of null
file:///.../src/presentation/ui/qml/CheckboxList/CheckboxList.qml:10:5: TypeError: Cannot read property 'width' of null
```

Đây **không phải** tiếng ồn lúc teardown mà `src/presentation/ui/qml/host.py`'s module docstring đã ghi nhận là "vô hại, đo được, không đáng sửa" (loại đó xảy ra khi Python huỷ ViewModel lúc app thoát/dialog bị garbage-collect, và đi kèm một lỗi thứ hai đọc thẳng `vm.<gì đó>` bị `null`). Ở đây chỉ có đúng 1 loại lỗi (`width` ở dòng 10), lặp lại tại **lúc mở dialog**, không phải lúc đóng — tái hiện được 100% mỗi lần mở, đã xác nhận trực tiếp bằng cách chạy lại `tests/unit/presentation/ui/qml/test_stat_grid_and_checkbox_list_bodies.py -s` trên môi trường Linux thật (PySide6 6.11.1 + `sagittarius_engine`, offscreen).

## 2. Nguyên nhân gốc rễ (Root Cause)

- `CheckboxList.qml` (dòng 10, trước sửa) và `StatGrid.qml` (dòng 12, trước sửa) đều khai root item với `width: parent.width`.
- Cả hai file **luôn luôn** được nạp làm **root object** của một `QQuickWidget` (`src/presentation/ui/qml/host.py`'s `QmlOverlay.__init__`: `self._quick.setSource(QUrl.fromLocalFile(str(qml_file)))`), với `setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)`.
- `SizeRootObjectToView` khiến `QQuickWidget` tự `setWidth()`/`setHeight()` **trực tiếp** lên root item mỗi khi widget đổi kích thước — nó không bao giờ *reparent* root item vào một `Item` cha nào trong scene QML. Vì vậy `parent` của root item **luôn là `null`** trong suốt vòng đời của nó, không phải chỉ lúc huỷ.
- Binding `width: parent.width` do đó đọc `.width` trên `null` ngay tại lúc `Component.completed`, mỗi lần dialog được mở — ném `TypeError` ra `stderr` (Qt Quick không dừng cả component vì 1 binding lỗi, nên dialog vẫn hiển thị đúng nhờ `SizeRootObjectToView` ghi đè `width` ngay sau đó — nhưng lỗi vẫn bị log, đúng như log user gửi).
- So sánh với `SelectList.qml` (cùng nhóm 4 file `Capital`/`SelectList`/`StatGrid`/`CheckboxList` dùng chung 1 khuôn theo `EPIC-015` §4c): root của nó (`ScrollView`) **không** có binding `width: parent.width` nào cả — mọi `width` bên trong chỉ tham chiếu `root.width` (chính nó), không phải `parent.width`. Đây đúng là khuôn đúng; `CheckboxList`/`StatGrid` đã lệch khỏi khuôn đó.

## 3. Cách khắc phục (Fix)

Xoá dòng `width: parent.width` khỏi root item ở cả hai file — không cần thay bằng gì khác, vì `SizeRootObjectToView` đã tự set `width` trực tiếp lên root, và mọi binding con bên trong đã tham chiếu `root.width` (chính root item, notifiable), không phải `parent.width`:

1. [`src/presentation/ui/qml/CheckboxList/CheckboxList.qml`](../../../src/presentation/ui/qml/CheckboxList/CheckboxList.qml) — xoá `width: parent.width` ở root `Column` (dòng 10 cũ).
2. [`src/presentation/ui/qml/StatGrid/StatGrid.qml`](../../../src/presentation/ui/qml/StatGrid/StatGrid.qml) — xoá `width: parent.width` ở root `Grid` (dòng 12 cũ), cùng cơ chế, cùng cách nạp qua `QmlOverlay`, phát hiện trong lúc soát nguyên nhân gốc của lỗi `CheckboxList` (chưa có trong log user gửi, nhưng cùng khiếm khuyết — để lại sẽ chỉ là vấn đề thời gian trước khi ai đó mở `ExtendedMetricsDialog`/`StatGrid` và thấy đúng lỗi này).

**Không đụng tới** lỗi `TypeError: Cannot read property 'rows'/'cards' of null` xuất hiện lúc **teardown** (khi `dialog.close()` + Python GC thu hồi ViewModel) — đó là lớp lỗi khác (`vm` context property bị null lúc huỷ scene, cùng họ với `BUG-069` đã sửa ở `DatabaseStatusTable`), không nằm trong log user báo, và cần null-guard riêng (`vm ? vm.rows : []`) cho từng binding đọc `vm.*` — để lại làm việc riêng nếu cần.

## 4. Kiểm thử xác minh (Verification)

Thêm 2 test vào `tests/unit/presentation/ui/qml/test_stat_grid_and_checkbox_list_bodies.py`:
`test_stat_grid_construction_does_not_throw_on_the_root_items_width_binding` và
`test_checkbox_list_construction_does_not_throw_on_the_root_items_width_binding` — dùng
`qInstallMessageHandler` bắt mọi message Qt phát ra **chỉ trong lúc construct + show** (gỡ handler
trước `dialog.close()` để không lẫn với nhiễu teardown đã biết), assert không có `TypeError` nào.

Chạy thật trên Linux (venv riêng, `PySide6==6.11.1` + `sagittarius_engine` clone từ
`anhembedded/Sagittarius_Engine`, `QT_QPA_PLATFORM=offscreen`):

- **Trước sửa** (`pytest ... -k width_binding`): **2 failed** — đúng lý do, log bắt được đúng
  `CheckboxList.qml:10:5` / `StatGrid.qml:12:5` `TypeError: Cannot read property 'width' of null`.
- **Sau sửa**: `tests/unit/presentation/ui/qml/` — **100 passed** (không còn dòng `width` nào trong
  stderr, chỉ còn các dòng `rows`/`cards`/`Theme` của null ở teardown — lớp lỗi khác, không đổi).
- `tests/unit/presentation/ui/screens/test_order_execution_modal.py` (dialog thật dùng
  `CheckboxList.qml` qua `OrderExecutionDialog`) — **3 passed**.
- `ruff check` + `ruff format --check` trên file test đã sửa: sạch.
