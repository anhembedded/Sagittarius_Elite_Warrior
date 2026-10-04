# EPIC-033J — Database is a workbench: shard table central, Sync dock, actions in menu and context menu

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟡 — a shared surface changes shape
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033C, EPIC-033D, EPIC-033F

---

## 1. Context and problem
Data Management is a `PageShell` page with metric cards, a custom header holding Vacuum and Purge, and five full-width 40 px action buttons in a scrolling column whose fifth is hidden (`data_management_view.py:433,71`; UX-06).

## 2. Acceptance criteria
- [ ] Shard table central; a Sync dock holds the symbol, timeframe and range form; Scan, Sync, Inspect, Clear, Vacuum and Purge are actions in a Database menu, the toolbar and the table's context menu, Purge and Clear behind confirmation.
- [ ] Record count and database size go to the status bar.
- [ ] The mode's conformance rows are removed.

## 3. Design
A database client's object list with context actions (P5).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/market_data/ui/` | Rebuilt on the workbench host |

## 5. Testing
Integration: conformance suite; the existing data-management journeys.

## Implementation notes (written when done)
Not started.
