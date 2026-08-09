# Nhiệm vụ: UI Preview Convention — "mỗi View có 1 file mock preview" + tool auto-discover

## 1. Mục tiêu (Objective)
Biến việc preview 1 màn QML từ 1 script ad-hoc (`scripts/preview_qml.py` hiện tại, viết
trong phiên `BOT-030`) thành **1 convention chính thức của kiến trúc UI**: mỗi View có
thể preview được thì phải có 1 file mock-data cùng cấp theo đúng 1 interface chuẩn, và
tool preview **tự quét thư mục UI để phát hiện** các View đó — không còn danh sách cứng
phải tự tay cập nhật mỗi khi thêm màn hình mới.

Đây là task do **user chủ động đề xuất** (không phải phát hiện từ code), sau khi xem
`scripts/preview_qml.py` và nhận xét nó quá specific — "hay tao thang 1 cho che... roi
tao no thanh rule cua UI arrchicture luon... co the scan UI dir de nhan biet dc co cac
view nao". User **chủ động chọn hoãn lại** ("toi co nhieu viec uu tien hon") — task này
tồn tại chỉ để 1 agent khác cầm lên làm sau, không phải việc cần làm ngay.

## 2. Bối cảnh (Context)
`BOT-030` (đã hoàn thành, xem `Tasks/completed/BOT-030_full_qml_migration.md` và
`Docs/Diagrams/ui_architecture.md`) đưa toàn bộ UI sang QML trừ `ChartCard`. Prototype
đầu tiên của preview tool ra đời ngay sau đó: `scripts/preview_qml.py` — 1 dict cứng
`_SCREENS = {"sidebar": _preview_sidebar, "settings": _preview_settings, "database":
_preview_database, "devboard": _preview_devboard}`, mỗi hàm tự tạo `create_quick_widget()`
+ 1 ViewModel thật (mọi ViewModel trong kiến trúc này vốn pure, không cần `IConfig`/
`IDispatcher`/`IThreadManager` — xem `Docs/Diagrams/ui_architecture.md` §3) + đổ vài
dòng data mẫu + load đúng file `.qml` của màn đó. Đã test chạy thật cả 4 màn, mở cửa sổ
sống, tương tác được, 0 lỗi QML.

**Vấn đề của bản hiện tại**: hàm preview của từng màn nằm hết trong `scripts/`, tách
biệt khỏi code của chính màn đó (`dashboard_view.py`, `settings_view.py`, ...). Thêm 1
màn mới (hoặc xoá 1 màn) đòi phải nhớ tự tay sửa `scripts/preview_qml.py` — không có gì
nhắc nếu quên, không có convention chính thức nào ràng buộc "mỗi View phải preview
được".

## 3. Thiết kế đề xuất (Design)

### 3.1. Convention: file `preview.py` cùng cấp mỗi package màn hình
Mỗi package UI preview-able được có 1 file `preview.py` nằm ngay trong package đó
(cùng cấp `*_view.py`/`*_presenter.py`), export đúng 1 hàm:

```python
def build_preview() -> QWidget:
    """Trả về 1 QWidget đã sẵn sàng .show() — tự tạo ViewModel + đổ mock data +
    load đúng file .qml của màn này. Không được phụ thuộc IConfig/IDispatcher/
    IThreadManager hay bất kỳ Presenter thật nào — preview luôn phải chạy được
    mà không cần boot Sagittarius Engine."""
```

4 file cần tạo (retrofit trực tiếp từ 4 hàm `_preview_*` đã có sẵn trong
`scripts/preview_qml.py` hiện tại — copy logic, không viết lại từ đầu):

| File mới | Lấy logic từ hàm hiện tại |
|---|---|
| `src/presentation/ui/components/sidebar/preview.py` | `_preview_sidebar()` |
| `src/presentation/ui/screens/settings/preview.py` | `_preview_settings()` |
| `src/presentation/ui/screens/data_management/preview.py` | `_preview_database()` |
| `src/presentation/ui/screens/dashboard/preview.py` | `_preview_devboard()` |

**Vì sao tên file cố định `preview.py` (không phải suffix `<tên>_preview.py`)**: mỗi
package UI hiện đã tự chứa đúng 1 View — glob theo tên file cố định trong mỗi thư mục
đơn giản và không mơ hồ hơn glob theo suffix.

### 3.2. Discovery: `scripts/preview_qml.py` viết lại thành scanner
Thay dict `_SCREENS` cứng bằng:

```python
def discover_previews() -> dict[str, Callable[[], QWidget]]:
    """Glob src/presentation/ui/**/preview.py, import từng module, lấy
    build_preview của nó. Khoá = tên thư mục cha (vd. "dashboard", "settings",
    "data_management", "sidebar") — khớp đúng route key hiện có của
    PresenterManager cho 3/4 màn (sidebar không phải route, nhưng dùng chung
    key "sidebar" cho nhất quán)."""
```

CLI giữ nguyên UX hiện tại (`python scripts/preview_qml.py <key>`), cộng thêm
`--list` để in ra mọi key tìm được (thay vì phải đọc code mới biết có gì) — quan
trọng vì giờ danh sách không còn cố định trong 1 dict nhìn thấy ngay được nữa.
`scripts/preview-qml.ps1` bỏ `-ValidateSet` cứng (không còn khớp thực tế), chuyển
sang forward thẳng argument, để Python tự validate + gợi ý qua `--list` khi sai.

### 3.3. Guard test — chính là "rule" được thực thi, không chỉ ghi trong docs
Thêm `tests/unit/presentation/ui/test_preview_fixtures_exist.py`, theo đúng phong
cách AST/glob thuần (không cần `qapp`) đã dùng ở `test_card_layer_structure.py` và
`test_qss_selectors_are_alive.py`:

- Test 1 (bắt buộc, nhanh): mọi thư mục con của `screens/` (trừ `_qml_shared`) +
  `components/sidebar/` phải có `preview.py` chứa 1 hàm `build_preview`. Fail rõ
  ràng, liệt kê thư mục nào thiếu — đây là cơ chế thật sự ngăn quên preview khi
  thêm màn mới, không phải chỉ ghi chú trong doc.
- Test 2 (nên có, chạy dưới `qapp`/offscreen): thật sự `import` + gọi
  `build_preview()` của từng file tìm được, assert không exception, và nếu widget
  trả về có `.errors()` (tức là 1 `QQuickWidget`) thì assert rỗng — biến việc
  "chạy thử preview_qml.py rồi nhìn xem có lỗi không" (cách verify thủ công hiện
  tại) thành 1 test tự động thật sự trong CI.

### 3.4. Cập nhật `Docs/Diagrams/ui_architecture.md`
Thêm mục **§11 — Preview convention**, mô tả rule ở §3.1 + trỏ tới guard test ở
§3.3 làm bằng chứng rule được enforce, không chỉ là văn bản. Theo đúng tinh thần
tài liệu hiện tại (mỗi rule kiến trúc đều có lý do + cách được enforce, không chỉ
mô tả suông).

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- **`ChartCard` KHÔNG nằm trong scope này.** Nó không phải QML, không routed qua
  `PresenterManager`, và cần OHLC data mẫu phức tạp hơn nhiều so với 1 ViewModel
  rỗng — nếu muốn preview riêng `ChartCard` sau này thì đó là 1 task khác, không
  tự động bị guard test ở §3.3 bắt buộc.
- Không mở rộng sang hot-reload (tự động load lại khi sửa file `.qml` trong lúc
  preview đang mở) — ngoài phạm vi, có thể đề xuất thành task riêng nếu cần sau.
- Giữ đúng ràng buộc đã chứng minh ở prototype: `build_preview()` không được đụng
  `IConfig`/`IDispatcher`/`IThreadManager`/Presenter thật — nếu 1 màn tương lai có
  ViewModel cần I/O thật để dựng (phá vỡ giả định "ViewModel luôn pure" ở
  `Docs/Diagrams/ui_architecture.md` §3), phải quay lại xem xét kiến trúc đó
  trước, không phải nới lỏng rule preview.
- Xoá 4 hàm `_preview_*` cũ khỏi `scripts/preview_qml.py` sau khi retrofit xong —
  không để trùng lặp logic giữa file mới và file cũ.

## 5. Phụ thuộc (Dependencies)
- `BOT-030` ✅ (Full QML Migration) — toàn bộ 4 View/ViewModel/QML file mà task
  này bọc preview quanh đều tạo ra từ đó.
- `scripts/preview_qml.py` + `scripts/preview-qml.ps1` (đã có sẵn từ phiên
  `BOT-030`, ngay sau khi đóng task) — là bản prototype cần refactor, đọc trước
  khi bắt đầu để tái dùng đúng logic mock-data đã verify chạy được, không viết
  lại từ đầu.
- `tests/unit/presentation/ui/test_card_layer_structure.py`,
  `tests/unit/presentation/ui/test_qss_selectors_are_alive.py` — 2 ví dụ guard
  test cùng phong cách (AST/glob, không cần Qt event loop) để tham khảo cách viết
  test ở mục 3.3.
