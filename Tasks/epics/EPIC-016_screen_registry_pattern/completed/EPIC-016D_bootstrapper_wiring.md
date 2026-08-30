# EPIC-016D — Cập nhật `app_bootstrapper.py`: đăng ký 4 module + wiring `sidebar_factory`

**Thuộc Epic:** [`EPIC-016`](../README.md)
**Trạng thái:** ✅ Xong 2026-08-30
**Phụ thuộc:** [`EPIC-016B`](../completed/EPIC-016B_registry_va_4_module.md) ✅, [`EPIC-016C`](EPIC-016C_main_window_decouple.md) ✅.

## Kết quả (2026-08-30)

Gộp chung với `016C` trong 1 commit — tách rời không có ý nghĩa để test độc
lập (MainWindow mới chỉ chạy được khi bootstrapper đã wiring registry
thật).

**Đúng như thiết kế:** `ScreenRegistry` dựng trong `app_bootstrapper.py`,
đăng ký 4 module thật, `sidebar_factory=Sidebar` (không cần lambda — chữ ký
`Sidebar.__init__(sections, bottom_actions, parent=None)` khớp thẳng
`Callable[[Sequence[NavSection], Sequence[NavItem]], ISidebar]`).

**Phát hiện thêm khi verify (ngoài dự kiến task):** `main_window.py`'s
`_NAV_SECTIONS`/`_BOTTOM_ACTIONS` có 3 consumer khác ngoài chính nó —
`tests/sanity/test_composition_root.py` (2 chỗ dựng `MainWindow` trực tiếp
+ `_navigable_routes()` đọc hằng số), `tests/integration/.../conftest.py`'s
`main_window` fixture, và `test_main_window_state.py`'s `_WindowHarness`.
Cả 4 đã sửa, thêm `real_screen_registry(container)` — hàm thuần (không phải
fixture, vì `test_composition_root.py` cần nó ở collection time) trong
`tests/conftest.py`, tái dùng ở cả 3 file test.

Verify thật (không phải `--collect-only`): sanity composition-root 8/8
(gồm navigate qua **cả 4 route thật**, kể cả Backtest — dựng full chart),
integration suite đầy đủ 42/42 (+4 skip có sẵn), 757 test `screens/`. Không
đổi assertion nào. Chi tiết đầy đủ ở message commit `9cf44d6`.

**Việc phát sinh ngoài scope, đã sửa vì chặn chính verification này:**
`backtest_presenter.py` import `DEV_MODE_CONFIG_KEY` qua compat shim đã
deprecated (`pyside_mvc.base_view` thay vì `pyside_mvc.mvc.base_view`) —
bug thật có từ trước, chỉ lộ ra vì đây là lần đầu tiên
`tests/sanity/test_composition_root.py` được **chạy thật** (chính file đó
tự ghi "NOT VERIFIED ... not one line has been executed"). Sửa 1 dòng, xác
nhận `DEV_MODE_CONFIG_KEY` không được re-export ở `pyside_mvc` top-level
(khác với thông báo deprecation gợi ý). 3 chỗ dùng shim khác
(`log_list_model`) **không sửa** — ngoài scope epic này, chỉ hiện thành
warning chứ không làm test nào đỏ ở đây.

---

## Việc cần làm

1. Trong `app_bootstrapper.py`, tạo 1 `ScreenRegistry`, gọi
   `register_module()` cho 4 `*ScreenModule` (`DashboardScreenModule`,
   `BacktestScreenModule`, `SettingsScreenModule`, `DatabaseScreenModule`)
   **trước khi** dựng `MainWindow`.
2. Cấp `sidebar_factory` cụ thể (dựng `Sidebar` thật từ
   `components/sidebar/sidebar.py`) cho constructor `MainWindow` mới.
3. Đây là **task duy nhất** trong epic này đụng bootstrap thật — chạy app
   thật (theo skill `run`) để xác nhận: nav hiển thị đúng thứ tự cũ, click
   chuyển màn hình đúng, route mặc định vẫn là Dev Board.

## Tiêu chí xong

- App khởi động, hiển thị Sidebar đúng y hệt thứ tự/label/icon trước khi
  có registry (so sánh ảnh chụp màn hình hoặc đối chiếu bằng mắt).
- Click từng mục nav chuyển đúng màn hình.
- `ci-local.ps1 -Full` xanh, log không có `FAILED|ERROR|Traceback`.
- Sau task này, hướng dẫn "thêm màn hình mới 3 bước" ở mục 8 tài liệu
  thiết kế phải đúng thật — thử thêm 1 module giả (không commit) để xác
  nhận không cần sửa `main_window.py`.
