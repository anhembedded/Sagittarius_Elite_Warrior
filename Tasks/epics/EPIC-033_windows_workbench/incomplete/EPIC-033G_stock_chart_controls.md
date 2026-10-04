# EPIC-033G — The chart is a canvas; its controls are actions in the toolbar and the context menu

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟡 — a shared surface changes shape
**Complexity:** M — the shared chart used by four modes
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033D

---

## 1. Context and problem
`ZoomControls` places six 32 px buttons over the plot with `setFixedSize` and `move()` (`zoom_controls.py:26,88,116-137`), covering the price axis; the timeframe row is a fixed-width strip of buttons that clips at 1366 px; "Hover to see data" takes a row of its own (`plot_layout.py:58`).

## 2. Acceptance criteria
- [ ] No widget is positioned over the plot; `ZoomControls` is deleted.
- [ ] Zoom, pan and reset work by wheel, drag and double-click; Zoom in/out/Reset are `QAction`s in the mode's chart toolbar and the plot's context menu.
- [ ] Timeframe is a checkable action group (or a combo box) in the toolbar, which overflows into its extension button instead of clipping.
- [ ] The hover readout goes to the status bar; no reserved row.
- [ ] Chart background, axes and grid take `QPalette` roles; only meaning colours (up/down candles, level markers) are explicit, through one named table.

## 3. Design
Every trading terminal zooms by wheel and drag; Qt's own `QToolBar` overflow solves the clipping (P5).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/charting/chart_card/` | Overlay removed, actions exposed, palette roles |
| Chart hosts in trading, backtesting, bots | Place the chart actions in their toolbar |

## 5. Testing
Unit: actions change the view range. Integration: conformance suite (no overlay widget, no clipping).

## Implementation notes (written when done)
Not started.
