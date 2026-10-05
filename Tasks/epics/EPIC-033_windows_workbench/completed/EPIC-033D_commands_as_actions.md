# EPIC-033D — Every command is one QAction contributed by its module: menu entry, toolbar button and shortcut share it

**Status:** ✅ Done (2026-10-05)
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟡 — a shared surface changes shape
**Complexity:** M — every command path in the app
**Epic:** [EPIC-033](../README.md)
**Depends on:** Engine W2; 033C

---

## 1. Context and problem
The tree has 8 `QAction`s (F9, Delete, four Database toolbar entries, two account-tab actions). Reload, Enable Trading and Emergency Stop are `QPushButton`/`StyledButton` widgets with `setFixedHeight(26)` (`dev_board_panel.py:278-336`), so the same command has no menu entry, no shortcut and a different look on each screen. HLD §11.5 promised a guard against a `QPushButton` that duplicates a `QAction`; it was never written.

## 2. Acceptance criteria
- [x] Every user command (reload, enable/disable trading, emergency stop, place order, cancel order, scan, sync, vacuum, purge, run backtest, export) is an `ActionDescriptor` contributed in its module's `contribute()`, with id, text, menu path, toolbar, shortcut and enabled-state binding.
- [x] Toolbars hold only actions; no `QPushButton` triggers a command that an action triggers (guard).
- [x] Destructive or money-moving actions (Emergency stop, Purge vault, Place order, Cancel all) confirm in a `QDialog` that names the consequence (HLD §11.5), enforced by a flag on the descriptor and a test.
- [x] Standard shortcuts are never rebound; a duplicate shortcut fails at contribution time.

## 3. Design
The Command pattern as Qt ships it: one `QAction` per command (Qt docs "Actions"). The registry is Engine mechanism (D3); handlers stay in presenters.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/*/module.py` | Action contributions |
| `src/modules/trading/ui/dashboard/dev_board_panel.py`, `dashboard_view.py` | Header buttons removed; actions used |
| `src/modules/market_data/ui/data_management_widgets/database_status_panel.py` | Toolbar actions become contributions |
| `tests/unit/architecture/test_commands_are_actions.py` | New guard |

## 5. Testing
Unit per module: the contributed actions, their shortcuts, their confirmation flag. Integration: each action reachable from the menu bar and triggering its presenter command.

## Implementation notes (written when done)
- **Mechanism.** A module declares `CommandContribution`s (`core/contracts/command_contribution.py`, plain data) in `contribute()`, Qt-free so a headless run imports no widget. The shell's `build_screen_registry` puts them in the `IScreenRegistry` beside the screens, so `MainWindow` cannot be given one without the other (five callers once passed only the screens). The window turns each into the Engine's `ActionDescriptor` (`presentation/ui/command_actions.py`), places toolbar commands on their mode's host, and hands the Engine's `ActionRegistry` to each presenter that is a `CommandPresenter` (`support/ui_kit/command_presenter.py`) as it builds the mode. A presenter binds through a small `*_command_binding.py` beside its declarations; `DerivedState` (`support/ui_kit/derived_state.py`) turns a view model's bare notify signal into the `Signal(bool)` a binding takes.
- **Why a base class, not a Protocol.** Every implementer is already a `BasePresenter`, so the ABC default applies; and the duplication ratchet excludes only names a shared base declares, so a Protocol left `bind_commands` counted once a second UI package implemented it (61 → 62).
- **Converted.** Desks (Enable live trading, Emergency stop F8); Dev Board (Reload history, Enable, Emergency stop, New order… F9); Data (nine commands in the Data menu, Sync timeframe Ctrl+L, Delete and Purge confirm); Backtest (Run F7 and Stop as two commands, Save/Import/Compare reports…, out-of-sample, Monte Carlo); Bots (New bot…, seven lifecycle commands, Refresh fills). A desk whose venue is off binds its two commands disabled (`DisabledDeskPresenter`). Place order and Cancel order/all stay the order panel's and the account tabs' own confirmed controls.
- **Guard.** `test_workbench_conformance.py::no_button_duplicates_a_command`: on the booted window, no push button in a mode is named like one of that mode's live commands; a restored "Run backtest" button turned it red.
- **Ratchets fell**: `setStyleSheet` calls 122 → 117; stock-control rows on the Dev Board panel, the Data view and the Backtest top panel; god files (Data view 714 → 576, Backtest top panel 887 → 734, Dev Board panel 637 → 574, three presenters); three conformance rows now pass.
- **Gaps, accepted.** (1) Enable live trading does not confirm: the Engine's confirmation asks on every trigger, so it would also ask before turning trading off. (2) A Bots lifecycle action no longer says why it is disabled: an action's tooltip is fixed by its declaration (the Start refusal still reads in the Parameters tab). (3) Fit levels and the chart's own controls are `EPIC-033G`'s. (4) Field choosers (symbol, timeframe, range buttons) are inputs, not commands, and stay buttons until `EPIC-033N`/the mode tasks.
