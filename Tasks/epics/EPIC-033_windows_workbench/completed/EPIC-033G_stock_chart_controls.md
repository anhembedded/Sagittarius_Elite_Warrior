# EPIC-033G — The chart is a canvas; its controls are actions in the toolbar and the context menu

**Status:** ✅ Done (2026-10-05)
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟡 — a shared surface changes shape
**Complexity:** M — the shared chart used by four modes
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033D

---

## 1. Context and problem
`ZoomControls` places six 32 px buttons over the plot with `setFixedSize` and `move()` (`zoom_controls.py:26,88,116-137`), covering the price axis; the timeframe row is a fixed-width strip of buttons that clips at 1366 px; "Hover to see data" takes a row of its own (`plot_layout.py:58`).

## 2. Acceptance criteria
- [x] No widget is positioned over the plot; `ZoomControls` is deleted. — `test_zoom_is_actions_on_the_toolbar_and_in_the_context_menu_not_widgets_on_the_plot` (no button under the plot widget); the "⏩ Live" overlay is the "Go live" action (`test_chart_card_viewport_follow_and_go_live`); the dev FPS label is a plain header label (`test_chart_fps_meter_is_hidden_until_dev_mode_is_enabled`).
- [x] Zoom, pan and reset work by wheel, drag and double-click; Zoom in/out/Reset are `QAction`s in the mode's chart toolbar and the plot's context menu. — `test_chart_card_zoom_actions_*`; `test_a_double_click_on_the_plot_resets_the_zoom` (real press–release–double-click–release, red with the connection removed).
- [x] Timeframe is a checkable action group (or a combo box) in the toolbar, which overflows into its extension button instead of clipping. — `test_dialog_and_timeframe_actions.py` (exclusive group); `test_a_narrow_toolbar_overflows_into_its_extension_button`.
- [x] The hover readout goes to the status bar; no reserved row. — `test_the_hover_readout_reaches_the_window_status_bar`.
- [x] Chart background, axes and grid take `QPalette` roles; only meaning colours (up/down candles, level markers) are explicit, through one named table. — `test_chart_chrome.py` (each role, a palette change repaints, red with the watcher disabled); `theme.py` is the table.

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
- **Actions, not widgets.** `chart_zoom_actions.py` (`ChartZoomActions`) owns Zoom in/out, the two vertical zooms, Box zoom (checkable, one drag) and Reset zoom; the toolbar shows four, the plot's context menu all six. A double-click inside the main view box triggers Reset zoom — pyqtgraph had no such gesture, so the old docstring's "double-click is pyqtgraph's" was wrong. `ViewportController`'s "⏩ Live" push button, moved over the plot's corner, is the "&Go live" action, disabled while the chart follows the live edge.
- **Timeframes.** `timeframe_picker/timeframe_actions.py` (`TimeframeActions`, an exclusive `QActionGroup` plus "More timeframes…") replaces `pill_row.py`; `ChartToolbar` is a `QToolBar`, so the style moves what does not fit into its extension menu. Its public surface (`sig_timeframe_changed`, `set_active`) is unchanged.
- **Readout.** `CrosshairController` reports plain text through a callback; `ChartCard` sends it as a `QStatusTipEvent`, which reaches the window's status bar. The label row above the plot is gone; the script info panel moved into row 0.
- **Chrome.** `chart_chrome.py`: `ChartChrome.from_palette` maps background → `Base`, axes/tick text/grid → `Text` (the grid is the axis pen at `GRID_ALPHA`), crosshair → `PlaceholderText`, axis tags → `ToolTipBase`/`ToolTipText`, and the pan preview's uncovered area → `Window`, so a blank band stays distinguishable from an empty plot (`test_long_drag_does_not_expose_a_large_blank_band` depends on it). `PaletteChangeWatcher` repaints on `QEvent.PaletteChange`. `theme.py` keeps the meaning colours only; `CROSSHAIR_COLOR` became `NEUTRAL_SERIES_COLOR` (out-of-sample divider, Monte Carlo paths). The last-price tag text uses the table's label colour; an uncoloured script info field takes the label's palette colour.
- **FPS.** `fps_overlay.py` → `fps_meter.py` (`ChartFpsMeter`): measures, writes a plain `QLabel` the card puts in its header; `release_viewport`/`watch_viewport` replace rebuilding it on the OpenGL fallback.
- **Guard precision.** `test_stock_controls_only.py` counted every `setCheckable`, including on a `QAction`, which `ui-presentation-rule.md` §6 names as the right form; it now skips a call on a name assigned from `QAction(...)` or a module function annotated `-> QAction`, with a probe test.
- **Size.** `ChartCard` would have grown past its ceiling; `BUG-034`'s diagnostic moved unchanged into `squashed_price_band_report.py` (`SquashedPriceBandReport`), still logging as `App.ChartCard`. `chart_card.py` 881 → 776 lines; the pure range tests left `test_cached_frame_interaction.py` for `test_cached_frame_ranges.py`.
- **Ratchets lowered:** stock controls (`zoom_controls.py`, `pill_row.py`, `fps_overlay.py` entries), app styling (style-sheet calls 115 → 114, files 21 → 20, palette files 32 → 26), god files.
- **Left for the mode epics:** the chart toolbar still sits in each `ChartCard`'s header, not in the window's toolbar area; 033H–L place it when they lay each mode out.
