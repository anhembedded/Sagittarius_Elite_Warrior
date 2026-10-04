# EPIC-033D — Every command is one QAction contributed by its module: menu entry, toolbar button and shortcut share it

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟡 — a shared surface changes shape
**Complexity:** M — every command path in the app
**Epic:** [EPIC-033](../README.md)
**Depends on:** Engine W2; 033C

---

## 1. Context and problem
The tree has 8 `QAction`s (F9, Delete, four Database toolbar entries, two account-tab actions). Reload, Enable Trading and Emergency Stop are `QPushButton`/`StyledButton` widgets with `setFixedHeight(26)` (`dev_board_panel.py:278-336`), so the same command has no menu entry, no shortcut and a different look on each screen. HLD §11.5 promised a guard against a `QPushButton` that duplicates a `QAction`; it was never written.

## 2. Acceptance criteria
- [ ] Every user command (reload, enable/disable trading, emergency stop, place order, cancel order, scan, sync, vacuum, purge, run backtest, export) is an `ActionDescriptor` contributed in its module's `contribute()`, with id, text, menu path, toolbar, shortcut and enabled-state binding.
- [ ] Toolbars hold only actions; no `QPushButton` triggers a command that an action triggers (guard).
- [ ] Destructive or money-moving actions (Emergency stop, Purge vault, Place order, Cancel all) confirm in a `QDialog` that names the consequence (HLD §11.5), enforced by a flag on the descriptor and a test.
- [ ] Standard shortcuts are never rebound; a duplicate shortcut fails at contribution time.

## 3. Design
The Command pattern as Qt ships it: one `QAction` per command (Qt docs "Actions"). The registry is Engine mechanism (D3); handlers stay in presenters.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/*/module.py` | Action contributions |
| `src/modules/trading/ui/dashboard/dev_board_panel.py`, `dashboard_view.py` | Header buttons removed; actions used |
| `src/modules/market_data/ui/data_management_widgets/database_status_panel.py` | Toolbar actions become contributions |
| `tests/unit/architecture/test_commands_are_actions.py` | New guard |

## 5. Testing
Unit per module: the contributed actions, their shortcuts, their confirmation flag. Integration: each action reachable from the menu bar and triggering its presenter command.

## Implementation notes (written when done)
Not started.
