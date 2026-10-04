# EPIC-033E — One Settings dialog with sections, OK, Apply and Cancel

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟡 — a shared surface changes shape
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**Depends on:** Engine W4; 033C

---

## 1. Context and problem
Settings is a sidebar route (`src/shell/settings/settings_screen.py`) rendering a scrolling page of group boxes, each with its own Save `StyledButton` (`trading_settings_view.py:238`, `market_data_settings_view.py:170`), and no Cancel. HLD §11.2 specifies one dialog, Qt Creator's Options shape.

## 2. Acceptance criteria
- [ ] Edit → Settings… (Ctrl+,) opens one `QDialog`: a section list on the left, the section page on the right, `QDialogButtonBox` OK / Apply / Cancel.
- [ ] Sections are contributed through `Place.SETTINGS_SECTION` as pages implementing the Engine's settings-page contract (apply, revert, dirty).
- [ ] Cancel discards every unapplied change; Apply is enabled only when a page is dirty; a page that fails validation keeps OK disabled and says why.
- [ ] The settings route and both Save buttons are deleted.

## 3. Design
Qt Creator Options / Visual Studio Tools → Options (P5).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/shell/settings/` | Route deleted; dialog wiring |
| `src/modules/trading/ui/settings/`, `src/modules/market_data/ui/settings/` | Pages implement the contract |

## 5. Testing
Unit: each page's apply/revert/dirty. Integration: open, edit, Cancel leaves config unchanged; Apply writes it.

## Implementation notes (written when done)
Not started.
