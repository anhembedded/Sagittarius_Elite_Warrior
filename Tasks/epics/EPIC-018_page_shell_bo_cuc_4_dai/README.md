# EPIC-018 — `PageShell`: bố cục 4 dải dùng chung cho mọi màn hình

**Trạng thái:** ✅ **Hoàn thành — 2026-08-30.** Cả 4 màn hình (Dev Board, Backtest,
Database, Settings) đã chuyển sang `PageShell`, verify bằng build app thật (offscreen,
dispatcher mock + seed dữ liệu) + chụp ảnh so sánh trước/sau, không chỉ đọc code.

## 1. Bối cảnh

User gửi ảnh chụp mockup thật vs. app đang chạy, phát hiện 3 vấn đề cụ thể:
1. Backtest chạy xong không thấy đâu là nút "Mở rộng chỉ số chi tiết" (mở
   `MetricsDetailPanel`, xây ở `EPIC-015` Phase 3).
2. Dev Board: tiêu đề header bị cắt chữ ("Developer Board (Live...").
3. User sau đó gửi thêm 1 trang "Pattern Library" — bản thiết kế chuẩn hoá: mọi màn hình
   trong App tab xếp đúng 4 dải theo thứ tự cố định, **đầu trang** (tên màn + phụ đề + hành
   động chính bên phải) → **thanh ngữ cảnh** (đang xem dữ liệu nào: symbol/TF/khoảng/múi
   giờ) → **vùng làm việc** (nội dung chính + rail 300px tuỳ chọn, **luôn bên phải, không
   bao giờ bên trái**) → **console** (log, cùng 1 component trên mọi màn). Ghi chú của
   chính trang đó: *"Dev Board mở thẳng vào chart với control ở rail-ish bên trái, Database
   để control bên trái và log trong cột phải, Backtest không có header — ba bộ khung trang
   khác nhau."* User: *"đó là triết lý layout của tất cả màn hình"*, giao toàn quyền thiết
   kế (*"bạn có thể cài bất cứ gì bạn thích"*), chỉ yêu cầu 1 abstraction chung áp ràng buộc
   thay vì mỗi màn tự vẽ khung riêng.

## 2. Chẩn đoán — 2 bug thật + 1 audit bố cục

Trước khi đụng tới layout, dựng app thật qua `app_bootstrapper.build()` (offscreen, patch
`create_app` để mock dispatcher + seed `IMarketDataRepository`), chụp `window.grab()` từng
màn — không đoán qua đọc code:

- **Bug thật #1 (`backtest_top_panel.py`):** `_sync_metrics_header()` (hiện thanh tiêu đề +
  nút "Mở rộng") chỉ nối `resultWarningTextChanged`, không nối `statCardsChanged`. Một lần
  chạy backtest không có cảnh báo overfit thì `resultWarningText` không đổi → tín hiệu không
  bắn → thanh tiêu đề (và nút Mở rộng bên trong) ở lại trạng thái ẩn ban đầu vĩnh viễn dù
  hàng stat card ngay dưới đã hiện. Sửa: nối thêm `statCardsChanged`. Test hồi quy tự verify
  bằng cách revert fix rồi chạy lại — fail đúng dòng assert, có fix thì pass.
- **Bug thật #2 (`dev_board_panel.py`):** `QLabel("Developer Board (Live Testbed)")` bị gán
  cứng `setFixedWidth(170)` — chữ dài hơn 170px nên bị cắt. Bỏ fixed-width, dùng size tự
  nhiên (row đã có `addStretch` sẵn nên không lệch).
- **Audit bố cục (4 màn):** Dev Board — tiêu đề chôn trong dải trên cùng của rail phải, không
  phải dải riêng full-width; Backtest — không có đầu trang, nút Run nằm chung hàng toolbar;
  Database — rail "SYNC CONTROLS" ở **bên trái** (đúng vi phạm luật "luôn bên phải"); Settings
  — đã có đầu trang đúng chuẩn từ trước.

## 3. `PageShell` — abstraction chung

`src/presentation/ui/kit/page_shell.py`, export qua `kit.PageShell`. Một `QWidget` composite
thuần (không vẽ nền/viền gì của riêng nó — `# base-exempt`, không phải `Surface`/`Card`),
4 dải cố định thứ tự trong `__init__`:

```python
shell.set_header(title, subtitle="", *, icon=None, actions=None)
shell.set_context_bar(widget | None)   # None = ẩn hẳn dải, không để trống
shell.set_workspace(main, rail=None)   # rail LUÔN là pane thứ 2 của QSplitter — không có
                                        # tham số nào đặt được rail bên trái
shell.set_console(widget | None)       # None = ẩn hẳn dải
```

Ràng buộc "rail luôn bên phải" được implement **cứng trong code** (chỉ 1 vị trí
`splitter.addWidget()` cho rail), không còn là quy ước bằng lời mỗi màn tự nhớ.

**Bug thật tìm được khi viết `PageShell` (không phải giả định lý thuyết):** bản đầu của
`set_workspace()` tạo `QSplitter()` **mới** mỗi lần gọi. Dev Board gọi `set_workspace()` hai
lần (lần đầu không rail lúc `_setup_ui()`, lần hai có rail lúc `set_view_model()`) — splitter
cũ bị `_clear_layout()` gỡ khỏi cây widget, không còn tham chiếu Python nào giữ nó → bị GC
ngay, và Qt cascade xoá theo **con của nó** (`scroll_area`) dù `DashboardView` vẫn giữ tham
chiếu Python tới `scroll_area` — next dùng thì `RuntimeError: libshiboken: Internal C++
object already deleted`. Bắt được bởi unit test (`test_dashboard_view.py`), không phải bởi
ảnh chụp — ảnh chụp trước đó vô tình chưa từng exercise đường gọi 2 lần này. Sửa: `QSplitter`
dựng **một lần** trong `__init__`, sống suốt vòng đời `PageShell`; `set_workspace()` chỉ gỡ
từng widget con hiện tại ra khỏi splitter (`setParent(None)` trên chính widget đó, không phải
trên một wrapper dùng-một-lần) rồi thêm widget mới vào.

Test: `tests/unit/presentation/ui/kit/test_page_shell.py` (8 case) + 1 entry trong
`tools/kit_showcase/showcase.py` (bắt buộc bởi `test_showcase_coverage.py`'s coverage guard).

## 4. Áp dụng cho 4 màn hình — theo thứ tự rủi ro tăng dần

- **Database** (`data_management_view.py`) — rủi ro thấp nhất, đúng vi phạm rõ nhất. Dời rail
  "SYNC CONTROLS" từ trái sang phải; bỏ `card.setFixedWidth(320)` (rail giờ nằm trong
  `QSplitter` co giãn được, không cần fixed nữa); "SYNC LOG" dời từ nested-trong-cột-phải
  thành dải console full-width riêng (khớp Dev Board/Backtest đã có sẵn) — đổi luôn
  `setFixedHeight(190)` → `setMinimumHeight(190)` cho nhất quán triết lý "không fix size".
- **Settings** (`settings_view.py`) — bỏ khối header tự vẽ riêng (`BG_CARD_HEADER` + viền +
  bo góc, bọc toàn màn trong 1 `Panel`) để dùng chung `PageShell.set_header()` — đây chính là
  loại "viền/màu không cần thiết" khác hẳn 3 màn kia mà user phàn nàn, giờ về chung 1 kiểu.
- **Backtest** (`backtest_top_panel.py` + `backtest_view.py`) — tách nút "CHẠY BACKTEST"
  (`_btn_run`, giờ có thêm `run_button` property public) ra khỏi hàng toolbar, đưa vào
  `PageShell`'s header actions. Toolbar còn lại (symbol/strategy/TF/range/timezone/...) trở
  thành đúng nghĩa "thanh ngữ cảnh". Header dựng 2 lần: lần đầu không có nút Run lúc
  `_setup_ui()` (view_model chưa tồn tại), lần hai có nút thật lúc `set_view_model()`.
- **Dev Board** (`dev_board_panel.py` + `dashboard_view.py`) — rủi ro cao nhất, đúng như
  `EPIC-015` từng cảnh báo cho mọi thứ nằm cạnh chart thật. Tiêu đề dời hẳn ra khỏi
  `DevBoardPanel` (giờ `DashboardView` sở hữu, giống 3 màn kia). `DevBoardPanel` không tự vẽ
  header/log nữa — lộ ra `header_actions` (price ticker + `StatusPillWidget` + nút Reload) và
  `console_widget` (`AppLogPanel`) qua property public để `DashboardView` gom vào
  `PageShell`. `DevBoardPanel` giờ đúng nghĩa là **rail**, không phải page header.

Mỗi bước: sửa → build app thật offscreen → chụp so sánh trước/sau → chạy full test suite của
đúng màn đó → mới sang màn kế. Full gate cuối (`tests/unit/ + tests/sanity/ +
tests/integration/`, `-n 6`): 2818 passed, 1 fail khác nhau mỗi lần chạy lại (đã cô lập chạy
riêng, luôn pass — flaky tải song song đã biết từ trước, không phải regression).

## 5. Không nằm trong epic này

- Chưa thêm "thanh ngữ cảnh" cho Dev Board — chart tự có toolbar riêng (symbol/TF) nằm trong
  vùng làm việc chính, không phải dải page-level; đụng vào là đụng đúng khu vực chart-adjacent
  `EPIC-015` xếp rủi ro cao nhất, để nguyên cho lần khác nếu cần.
- Indicators panel (Dev Board) bị cắt sau EMA 200, cần cuộn mới thấy 4 chỉ báo còn lại (MACD/
  EMA Ribbon/EMA Cross/DEV scripting) — xác nhận **không phải bug**: cả 9 script đăng ký đúng,
  scrollbar thật có và hoạt động được. Không sửa trong epic này (sửa sẽ cần thu gọn/redesign
  System Controls, phạm vi khác một bug thật).
- Border trên mỗi ô KPI của `MetricsDetailPanel` (khác `StatCard` chính không viền) — kiểm tra
  bằng ảnh chụp thật, trông có chủ đích (khớp `NOTES.md`), không sửa.
