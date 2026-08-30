# EPIC-016C — Đổi `MainWindow` nhận `IScreenRegistry`/`ISidebar`/`sidebar_factory`

**Thuộc Epic:** [`EPIC-016`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu — phụ thuộc `016B`
**Phụ thuộc:** [`EPIC-016B`](EPIC-016B_registry_va_4_module.md) (registry + 4 module phải tồn tại trước).

---

## Việc cần làm

Theo mục 6 của [`Docs/SCREEN-REGISTRY-PATTERN/README.md`](../../../../Docs/SCREEN-REGISTRY-PATTERN/README.md):

1. Đổi constructor `MainWindow` nhận `screen_registry: IScreenRegistry`,
   `sidebar_factory: Callable[[Sequence[NavSection], Sequence[NavItem]], ISidebar]`
   thay vì tự dựng `Sidebar` cụ thể.
2. Xoá `_NAV_SECTIONS`, `_BOTTOM_ACTIONS`, `_setup_router()` hard-code.
3. `switch_screen()`/`select_section()` chỉ gọi qua `ISidebar`/`IScreenRegistry`
   — `MainWindow` không còn import bất kỳ View/Presenter cụ thể nào.
4. Route mặc định lấy qua `self._registry.get_default_route()` (không hard-code
   `"dashboard"`).

## Ràng buộc

- **Không đổi hành vi UX.** Đây không phải dịp đổi thứ tự nav, đổi default
  route, hay đổi cách restore state (`UiStateCoordinator` giữ nguyên).
- File này sau khi sửa vẫn phải nằm dưới ngưỡng review 400 dòng của
  `architecture-rule.md` §5 — nếu nó phình ra vì logic dựng central layout,
  tách phần đó ra helper riêng, không nhét hết vào constructor.

## Tiêu chí xong

- `main_window.py` không còn dòng import nào tới `screens/dashboard`,
  `screens/backtest`, `screens/settings`, `screens/data_management`.
- Toàn bộ test hiện có liên quan tới `MainWindow` (nav order, default
  route, switch screen) vẫn xanh không sửa assertion — chỉ sửa cách dựng
  fixture nếu cần đổi constructor signature.
- `test_no_cross_screen_imports.py`/`test_screen_layer_structure.py` vẫn xanh.
