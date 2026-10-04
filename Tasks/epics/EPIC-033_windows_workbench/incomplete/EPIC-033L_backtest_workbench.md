# EPIC-033L — Backtest is a workbench and its sixteen dialogs are stock dialogs

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🔴 — touches order placement
**Complexity:** L — the most styled area (61 `setStyleSheet` calls)
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G

---

## 1. Context and problem
Backtest is a `PageShell` page whose parameter bar of pill dropdowns clips at 1366 px, with a 120 px empty frame, a page scroll around a chart scroll, and 16 modal files under `backtest_modals/` styled by hand; `backtest_top_panel.py` alone has 25 `setStyleSheet` calls.

## 2. Acceptance criteria
- [ ] Chart central; parameters (market, symbol, strategy, timeframe, range, timezone, capital, execution) in a toolbar that overflows, or one Run settings dialog; Run is an action (F5); results, trades and metrics are docks.
- [ ] Every backtest dialog is a stock `QDialog` with `QDialogButtonBox`, a title naming the action and validation before OK.
- [ ] No `setStyleSheet` left under `src/modules/backtesting/`; the mode's conformance rows are removed.

## 3. Design
IDE run configurations: a toolbar plus a run-settings dialog (P5).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/backtesting/ui/` | Rebuilt; presenters, coordinators and view models kept |

## 5. Testing
Unit: dialogs validate. Integration: conformance suite; the existing backtest journeys.

## Implementation notes (written when done)
Not started.
