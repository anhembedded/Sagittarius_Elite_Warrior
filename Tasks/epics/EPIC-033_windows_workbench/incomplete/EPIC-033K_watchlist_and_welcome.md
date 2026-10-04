# EPIC-033K — Watchlist and Welcome follow the contract

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟢 — a shared surface changes shape
**Complexity:** S
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033C

---

## 1. Context and problem
Watchlist is a `PageShell` page whose Symbol column takes ~880 px while numeric columns are cramped; Welcome renders black text on a near-black background (UX-04).

## 2. Acceptance criteria
- [ ] Watchlist: table central with numeric columns right-aligned and sized to content, Symbol sized to content; header state remembered.
- [ ] Welcome: platform colours, name, version, Start; no custom background.
- [ ] Both modes' conformance rows are removed.

## 3. Design
Stock `QTableView` header sizing (`ResizeToContents` / `Stretch` on the last section).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/market_data/ui/watchlist/`, `src/shell/welcome/` | Rebuilt |

## 5. Testing
Integration: conformance suite; screenshot check.

## Implementation notes (written when done)
Not started.
