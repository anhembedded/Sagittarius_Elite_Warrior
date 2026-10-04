# EPIC-033F — One Output dock with a channel per module replaces three log cards

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟢 — a shared surface changes shape
**Complexity:** S
**Epic:** [EPIC-033](../README.md)
**Depends on:** Engine W4; 033C

---

## 1. Context and problem
System monitor, Sync log, Futures/Spot log and the backtest log are four `AppLogPanel(LogPanel(Card))` instances (`app_log_panel.py:74`), each with its own title header, badge, Copy/Clear and fixed placement; inside a dock the card header duplicates the dock title (UX-05, UX-11).

## 2. Acceptance criteria
- [x] One bottom dock "Output" for the window (see the notes), with a channel combo box (as in Visual Studio's Output window); modules contribute channels (their existing `LogListModel`).
- [x] Copy and Clear are actions of the dock; the four log cards and `LogPanel`/`AppLogPanel` are deleted.
- [x] The dock is shown and hidden from the menu bar (Window, see the notes) and remembered by the perspective.

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
- **One pane for the window, not one per mode.**
  - The Engine's `WorkbenchShell.set_output_pane()` docks a single `OutputPane` at the bottom of the main window, as Visual Studio has one Output window. Its toggle is under Window, because it belongs to no mode. View lists the showing mode's own docks.
  - Its visibility and place are saved with the window's state (`saveState`), so it is remembered without a per-mode perspective.
  - Showing a mode brings that mode's channel forward. A mode with no log leaves the channel that is showing.
- **How a screen offers its log.**
  - `support/ui_kit/output_source.py` defines `IOutputSource.output_channel() -> OutputChannel | None`. It is a `Protocol`, reason (a), because the implementers are views. It lives in `support/ui_kit`, not `core/contracts`, because it names the Engine's `OutputChannel`.
  - `None` is a real answer: a desk whose venue is disabled in this run builds no view model, so it keeps no log. The integration fixture runs with both venues off, which is how this was found.
  - `support/ui_kit/output_source_view.py` (`OutputSourceView`) implements it once. A view sets `_output` when its view model is bound. Without that shared base, `output_channel` defined in three UI packages raised the duplication ratchet 61 → 62.
- **Channels:** System monitor (Dev Board), Futures and Spot (each enabled desk), Sync (Data) and Backtest. Backtest's "Backtest log" tab is gone from its results panel; an old `logs` tab id falls back to Trades, as any unknown id does.
- **Deleted:** `support/ui_kit/app_log_panel.py`, `kit/surfaces/log_panel.py` with its two test files, the kit showcase's log samples, and the Dev Board's System monitor dock.
- **Baselines lowered:**
  - styling: `apply_role` calls 40 → 39, files 21 → 20, palette files 33 → 32;
  - stock controls;
  - god files: backtest results panel, Data view and Dev Board panel, plus one test file.
- **Proof:**
  - `tests/unit/presentation/ui/test_main_window_output.py` uses a real `ScreenRegistry`, the real `OutputPane` and real `LogListModel`s: one channel per screen with a log, in mode order; a screen with no log this run is skipped; showing a mode brings its channel forward; a line reaches the pane. Removing the switch turns two tests red.
  - `tests/integration/presentation/ui/test_output_pane.py` runs on the real window: the channel set equals the screens with a log plus the enabled desks, there is one pane, and a line the Data screen logs is shown on its channel.
  - `tests/unit/modules/trading/ui/desk/test_desk_screen.py` checks each desk's channel and the disabled desk's `None`.
  - The Dev Board walkthrough clears its log through the pane's Clear action.
