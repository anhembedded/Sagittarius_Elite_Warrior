# BOT-153 — The Market mode edits an indicator script's parameters

**Status:** ✅ Done (2026-10-05)
**Source:** the owner, 2026-10-05, relayed by the coordinating session of EPIC-033: the Dev Board's indicator parameters must not go with it, "Thêm vào Market" (add it to Market), as its own small PR before `EPIC-033P` stage 3 deletes the Dev Board
**Risk:** 🟢 — one command over the dialog and sink `BOT-063` already proved
**Complexity:** S — a command, a selection, a redraw
**Epic (optional):** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md) (unblocks `EPIC-033P` stage 3)
**Depends on:** EPIC-033H (merged)

---

## 1. Context and problem
The Dev Board is the only screen that edits an indicator script's parameters: `BOT-063` gave each script of its Indicators list a parameters button (`src/modules/trading/ui/dashboard/dev_board_panel.py`, `_open_script_params_dialog`) that opens `StrategyParamsDialog` over an `IndicatorScriptParamsSink`. The Market mode reads the saved parameters (`market_dependencies.py`, `script_params`) but cannot edit them, and `EPIC-033P` deletes the Dev Board.

## 2. Acceptance criteria
- [x] Tools → Indicator parameters… opens the parameters of the script selected in the Market mode's Indicators panel, in the same dialog.
- [x] Off with no script selected, for a script that declares no input, and with no store to save to; triggered anyway, it opens nothing.
- [x] Opening it does not crash and parents the dialog to a widget (the `BOT-063` regression).
- [x] Saved values redraw the open charts that draw the script.

## 3. Design
One `QAction` (`ui-presentation-rule.md` §6) in Tools beside Options, as a dialog of settings, scoped to the Market mode; not a button per list row, which the rule forbids repeating a command. A presenter-owned `IndicatorParamsCommand` decides when it may run and emits `edited` once the dialog closes; the presenter redraws the charts drawing that script, whose new instances read the saved values (`script_params`).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/market/indicator_params_command.py` (new) | the command's state and opening |
| `src/modules/trading/ui/market/market_commands.py` | `INDICATOR_PARAMS` in Tools |
| `src/modules/trading/ui/market/market_view.py` | the selected script, `indicator_selected`, the dialog |
| `src/modules/trading/ui/market/market_presenter.py`, `market_chart.py` | the binding and the redraw |
| `src/modules/trading/ui/market/market_dependencies.py` | `params_store`, the store `script_params` reads |

## 5. Testing
Unit: `test_market_indicator_params.py` ports the Dev Board's four tests (`test_dev_board_indicator_params.py`) to the command and adds the redraw; `test_market_dependencies.py` proves the command saves where the charts read. Sanity boots the real window with the new Tools item.

## Implementation notes (written when done)
- **Placement:** Tools → &Indicator parameters…, scoped to the Market mode, "…" because the dialog asks for values. I is no other Tools item's key; the Engine refuses a clash at build and the sanity tier boots the window.
- **The four Dev Board tests, ported:** enabled only for a selected script with inputs (EMA 20 on, EMA cross off, nothing selected off); opening does not crash and the dialog's parent is a widget titled "Indicator Parameters"; without a store the command is off and opens nothing (the Market's form of "a no-op before injection": its store comes with the dependencies); a script without inputs opens nothing.
- **Added:** a saved period (5 for EMA 20) redraws the open chart's EMA line with the new value; `market_dependencies_for` hands the command the same store the charts read.
- **Verification:** commit tier PASS; the Market tests and the sanity tier pass; mutation-checked (the inputs check, the store check, the open guard, the selection signal, the redraw connection, the widget parent, the binding, the shared store each turn a test red).
- **Still open:** the dialog is the kit's `StrategyParamsDialog` (an `Overlay` with styling), carried over as the Dev Board used it; its rebuild with stock controls is `EPIC-033M`'s.
