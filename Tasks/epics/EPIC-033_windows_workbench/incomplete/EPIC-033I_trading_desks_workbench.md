# EPIC-033I — Futures and Spot desks are workbenches: chart central, Order, Account and Strategy docks

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🔴 — touches order placement
**Complexity:** L — the money-moving screens
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G

---

## 1. Context and problem
Each desk is a `PageShell` page (`desk_view.py:111`) with a fixed splitter, an order form inside its own scroll area, a dark Strategy card inside a light form, and a log card fixed at the bottom; the order form spreads its rows apart when given height (UX-03, UX-07).

## 2. Acceptance criteria
- [ ] Each desk is a workbench mode: chart central; docks Order entry, Account (positions/holdings, open orders), Strategy; Output channel for the venue.
- [ ] The order form is a top-aligned `QFormLayout` with bounded field widths; no scroll area inside the dock unless the dock itself is smaller than the form.
- [ ] Every order command is an action with its confirmation dialog (033D); the disabled-venue state is a central message with the action that enables it, not a full-screen panel.
- [ ] Testnet journeys of `EPIC-028` still pass; the mode's conformance rows are removed.

## 3. Design
MT5 / TWS: chart central, order entry and account in dockable panels (HLD §11.2).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/` | Rebuilt on the workbench host; presenters and view models kept |

## 5. Testing
Unit: desk view wiring. Integration: conformance suite and the existing desk journeys. Testnet: the user confirms one order round-trip per venue.

## Implementation notes (written when done)
Not started.
