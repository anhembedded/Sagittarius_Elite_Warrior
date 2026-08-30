# EPIC-016B — Dựng `registry/` + viết 4 `*ScreenModule` cho màn hiện có

**Thuộc Epic:** [`EPIC-016`](../README.md)
**Trạng thái:** ✅ Xong 2026-08-30
**Phụ thuộc:** [`EPIC-016A`](../completed/EPIC-016A_xac_nhan_voi_engine_that.md) ✅

## Kết quả (2026-08-30)

Dựng đầy đủ `registry/` (`models/`, `ports/`, `screen_registry.py`,
`abstract_screen_module.py`), `ISidebar` (bỏ `select_section()`/
`set_navigation()` — không caller nào cần, giữ đúng tinh thần chống
speculative generality), và 4 `*ScreenModule` thật.

**Đối chiếu byte-for-byte** với `main_window.py`'s `_NAV_SECTIONS`/
`_BOTTOM_ACTIONS` cũ (script tay trước khi viết test cố định): giống hệt —
cùng thứ tự section, cùng label/route/icon, cùng default route (`dashboard`).
18 test mới (`ScreenRegistry` behaviour, `ISidebar` contract, tương đương
nav thật) — tất cả xanh trên venv 3.12 + PySide6 6.11.1 + engine thật.

**Sai khác so với thiết kế gốc:** `select_section()`/`set_navigation()` bị bỏ
khỏi `ISidebar` — không có trong `Sidebar` thật, không caller nào cần.

---

## Việc cần làm

Theo thiết kế ở [`Docs/SCREEN-REGISTRY-PATTERN/README.md`](../../../../Docs/SCREEN-REGISTRY-PATTERN/README.md)
mục 3, 4, 7, và ratify ở ADR D1/D2/D5/D6:

1. Tạo `src/presentation/ui/registry/` theo cấu trúc thư mục ở mục 7 của
   tài liệu thiết kế: `models/` (`NavMetadata`, `SectionDescriptor`,
   `ScreenDescriptor` — nội bộ registry, **không** lộ ra ngoài `ISidebar`,
   xem ADR D1), `ports/i_screen_registry.py`, `screen_registry.py`,
   `abstract_screen_module.py`.
2. `ScreenRegistry.register_module()` phải raise `ValueError` khi 2 module
   cùng `section_key` khai `section_sequence` khác nhau và không có
   `register_section()` tường minh (ADR D2 — fail fast, không âm thầm lấy
   giá trị module đăng ký trước).
3. `get()`/`get_default_route()` theo đúng hợp đồng lỗi ADR D5
   (`KeyError`/`RuntimeError`).
4. Tạo `src/presentation/ui/components/sidebar/ports/i_sidebar.py`
   (`ISidebar`, `Protocol`, `@runtime_checkable`) — docstring phải ghi lý
   do (b) đúng câu chữ (ADR D6), không phải "Shiboken metaclass". Thêm
   test hợp đồng hai chiều đối chiếu `ISidebar` ↔ `Sidebar` (tiền lệ
   `test_backtest_view_contract.py`).
5. Viết 4 module: `DashboardScreenModule`, `BacktestScreenModule`,
   `SettingsScreenModule`, `DatabaseScreenModule` (route
   `data_management`) — copy đúng nav metadata hiện có trong
   `main_window.py`'s `_NAV_SECTIONS`/`_BOTTOM_ACTIONS` (thứ tự, icon,
   label, is_default) để hành vi UX không đổi.
6. `create_view`/`create_presenter` của từng module: import concrete
   View/Presenter **bên trong hàm**, không ở top-level `module.py` (lazy
   import — đúng convention đã có trong repo cho các màn hình nặng như
   backtest/data_management).

## Tiêu chí xong

- 4 `*ScreenModule` build descriptor đúng nav hiện tại — đối chiếu từng
  field với `main_window.py` bản cũ, không suy đoán.
- `ScreenRegistry.build_sidebar_navigation()` trả về `NavSection`/`NavItem`
  (alias của `SidebarSection`/`ITab`) — không có type mới nào rò ra khỏi
  registry.
- Test hợp đồng `ISidebar` ↔ `Sidebar` xanh.
- `mypy`/`ruff`/test suite hiện có không đỏ thêm (registry là code mới,
  chưa có gì gọi nó cho tới `016C`, nên không phá hành vi cũ ở bước này).
