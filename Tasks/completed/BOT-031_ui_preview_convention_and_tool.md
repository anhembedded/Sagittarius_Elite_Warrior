# Nhiệm vụ: UI Preview Convention — "mỗi View có 1 file mock preview" + tool auto-discover

> Trạng thái: ✅ Đã hoàn thành (Completed)
> Thuộc Epic: Developer Experience & UI Architecture

## 1. Mục tiêu (Objective)
Biến việc preview 1 màn QML từ 1 script ad-hoc (`scripts/preview_qml.py` trước đây) thành **1 convention chính thức của kiến trúc UI**: mỗi View có thể preview được có 1 file `preview.py` cùng cấp theo đúng interface chuẩn (`build_preview() -> QWidget`), và tool preview **tự quét thư mục UI để phát hiện** các View đó.

## 2. Các thay đổi đã thực hiện
1. **Tạo file `preview.py` cho từng package UI**:
   - `src/presentation/ui/components/sidebar/preview.py`: Preview Sidebar với đầy đủ navigation sections.
   - `src/presentation/ui/screens/settings/preview.py`: Preview SettingsScreen với API & Credentials mock.
   - `src/presentation/ui/screens/data_management/preview.py`: Preview DatabaseScreen với table status và logs.
   - `src/presentation/ui/screens/dashboard/preview.py`: Preview DevBoardPanel với ticker, WS status, indicators.
   - `src/presentation/ui/screens/backtest/preview.py`: Preview Backtest screen đầy đủ metric cards, trade logs, limitations.
2. **Refactor `scripts/preview_qml.py` và `scripts/preview-qml.ps1`**:
   - `discover_previews() -> dict[str, Callable[[], QWidget]]` tự động glob `src/presentation/ui/**/preview.py`.
   - Hỗ trợ flag `--list` để liệt kê danh sách previewable components/screens.
   - Forwarding arguments động từ PowerShell wrapper.
3. **Guard Unit Tests (`tests/unit/presentation/ui/test_preview_fixtures_exist.py`)**:
   - `test_every_screen_and_sidebar_has_preview_file`: AST & filesystem verification rằng mọi UI package đều có `preview.py` và khai báo `build_preview()`.
   - `test_discover_previews_finds_all_targets`: Xác nhận auto-discovery tìm thấy toàn bộ 5 targets (`sidebar`, `settings`, `data_management`, `dashboard`, `backtest`).
   - `test_all_discovered_previews_build_cleanly`: Dựng từng preview trong môi trường offscreen Qt và assert 0 exceptions, 0 QML errors.

## 3. Kiểm tra xác nhận (Verification)
- Toàn bộ 3 tests trong `test_preview_fixtures_exist.py` pass 100%.
- Full CI test suite (`.\scripts\ci-local.ps1 -Full`) pass 100% với 0 warnings, 0 lint errors.
