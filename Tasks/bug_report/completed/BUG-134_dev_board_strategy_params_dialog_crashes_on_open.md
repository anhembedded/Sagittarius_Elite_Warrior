# BUG-134 — Dev Board's "Strategy Parameters" button crashes the moment it's clicked

- **Reported:** 2026-09-23 (found while implementing `BOT-063`'s per-indicator-script params dialog, which reuses this same `StrategyParamsDialog` class)
- **Severity:** 🔴 P1 — clicking "Strategy Parameters…" on the Dev Board raises an uncaught `TypeError`, so a live trader can never edit their armed strategy's parameters from that screen.
- **Status:** ✅ Fixed (2026-09-23)
- **Context:** Dev Board (live trading testbed) → `modules/trading` → `ui/dashboard/dev_board_panel.py`
- **Environment:** App on `claude/bot-112d-063-039-batch`, PySide6, `QT_QPA_PLATFORM=offscreen` (reproduces identically under a real display — the constructor rejects the argument type before any window ever needs to paint).

## Reproduction

1. Open the Dev Board screen.
2. Click the "Strategy Parameters…" button (`_btn_strategy_params`).
3. **Expected:** the Strategy Parameters dialog opens.
4. **Actual:** `_open_strategy_params_dialog()` raises `TypeError` inside `StrategyParamsDialog.__init__` → `Overlay.__init__` → `QDialog.__init__`, before any dialog is shown. 100% reproducible, every click.

## Symptom

```
TypeError: 'PySide6.QtWidgets.QDialog.__init__' called with wrong argument types:
  PySide6.QtWidgets.QDialog.__init__(DevBoardPanel)
Supported signatures:
  PySide6.QtWidgets.QDialog.__init__(parent: PySide6.QtWidgets.QWidget | None = None, f: PySide6.QtCore.Qt.WindowType = Default(Qt.WindowFlags), *, sizeGripEnabled: bool | None = None, modal: bool | None = None)
```
(reproduced directly against a minimal `QObject` in place of `DevBoardPanel`, isolating the mechanism before touching the real class.)

## Root cause

`dev_board_panel.py:758` (before the fix) called `StrategyParamsDialog(self._view_model.strategy, self)`, passing `self` — the `DevBoardPanel` instance — as the new dialog's Qt parent. `DevBoardPanel` stopped being a `QWidget` in `EPIC-025` PR 1.4c-3 (it now only *builds* the cards `DashboardView` places into docks; see the class's own docstring) and is a bare `QObject`. `StrategyParamsDialog` extends `Overlay(QDialog)`, whose constructor requires a `QWidget | None` parent — passing any non-widget `QObject` is rejected by PySide6/shiboken's overload resolution at the C++ boundary, not silently accepted.

The same class already has the fix pattern for its *other* two dialogs: `_dialog_parent()` (added for the symbol picker and time-range dialog) exists specifically because "these two dialogs used to be parented to `self`, which worked while this class was a widget... a `QDialog` parented to one raises `TypeError` — found by the existing tests, not by reading." `_open_strategy_params_dialog()` was never updated to use it, and nothing exercised the button end to end (`grep` across `tests/` for `_open_strategy_params_dialog`/`btnStrategyParams` found zero hits before this fix), so the gate never saw it fail.

## Fix

`dev_board_panel.py`, `_open_strategy_params_dialog()`: pass `self._dialog_parent()` instead of `self` as the dialog's Qt parent — the exact same fix `_open_symbol_picker()`/`_open_time_range_dialog()`-equivalent methods already apply for their own dialogs on this class.

## Regression test

`tests/unit/modules/trading/ui/dashboard/test_dev_board_indicator_params.py::test_open_strategy_params_dialog_does_not_crash` — patches `StrategyParamsDialog` at its real import path (a real `.exec()` is modal and would hang this offscreen test suite forever, the same hazard `test_app_bootstrapper_exception_handler.py` documents for `BUG-048`), calls the real `_open_strategy_params_dialog()` against a real `DevBoardPanel`, and asserts the parent passed to the dialog is not the panel itself. Failed before the fix with the constructor `TypeError` reproduced above (not a mocked stand-in for the crash — the real `Overlay`/`QDialog` chain, only the terminal dialog class is patched to avoid the modal `exec()`); passes after.

## Verification

```
cd /tmp/batch6-work/Sagittarius_Elite_Warrior && PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/modules/trading -q
```
767 passed (includes the new regression test and the full `modules/trading` tree, confirming no other consumer of `_open_strategy_params_dialog()`/`_dialog_parent()` regressed). `ruff check`/`ruff format --check` clean on the touched files.
