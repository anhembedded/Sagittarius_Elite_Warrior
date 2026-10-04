# EPIC-033H — Dev Board: plain panels, no card inside a dock, contributions only

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟡 — a shared surface changes shape
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G

---

## 1. Context and problem
Dev Board is the one workbench mode, but its docks wrap kit `Panel`s that repeat the dock title with `section_row(...)` (`layout_helpers.py:23`; five callers), its Indicators panel stretches a header over ~370 px at 1920×1080, and `DashboardView` places its own widgets by hand before module contributions (`dashboard_view.py:217-277`).

## 2. Acceptance criteria
- [ ] Every Dev Board panel is a plain widget (form, table or list) contributed through the registry; no `Card`, `Panel` or `section_row`.
- [ ] No header duplicates a dock title; nothing stretches into empty space at any tested size.
- [ ] The mode's conformance rows are removed from the baseline.

## 3. Design
HLD §11.3: a panel has a title, a close button and nothing else of its own.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/dashboard/` | Cards and hand-placed widgets replaced by contributions |

## 5. Testing
Integration: conformance suite for `dashboard`; screenshots before/after at 1024, 1366, 1920.

## Implementation notes (written when done)
Not started.
