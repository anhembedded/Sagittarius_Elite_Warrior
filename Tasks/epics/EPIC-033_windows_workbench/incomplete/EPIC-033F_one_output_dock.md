# EPIC-033F — One Output dock with a channel per module replaces three log cards

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟢 — a shared surface changes shape
**Complexity:** S
**Epic:** [EPIC-033](../README.md)
**Depends on:** Engine W4; 033C

---

## 1. Context and problem
System monitor, Sync log, Futures/Spot log and the backtest log are four `AppLogPanel(LogPanel(Card))` instances (`app_log_panel.py:74`), each with its own title header, badge, Copy/Clear and fixed placement; inside a dock the card header duplicates the dock title (UX-05, UX-11).

## 2. Acceptance criteria
- [ ] One bottom dock "Output" per workbench, with a channel combo box (as in Visual Studio's Output window); modules contribute channels (their existing `LogListModel`).
- [ ] Copy and Clear are actions of the dock; the four log cards and `LogPanel`/`AppLogPanel` are deleted.
- [ ] The dock is shown and hidden from View and remembered by the perspective.

## 3. Design
Visual Studio / VS Code Output pane (P5).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/ui_kit/app_log_panel.py`, `kit/surfaces/log_panel.py` | Deleted |
| Views that built a log card | Contribute a channel instead |

## 5. Testing
Unit: channel switching, copy. Integration: each module's messages appear in its channel.

## Implementation notes (written when done)
Not started.
