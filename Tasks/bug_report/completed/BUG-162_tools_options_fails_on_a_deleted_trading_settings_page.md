# BUG-162 — Tools → Options opens a "Critical System Error" instead of the Options dialog

- **Reported:** 2026-10-06 (the user, in chat, with two screenshots and the traceback)
- **Severity:** 🟡 P2 — the Options dialog does not open, so no setting can be changed from the app (Tools → Options is the one place for them, `ui-presentation-rule.md` §7)
- **Status:** Fixed (2026-10-06)
- **Renumbered:** filed as `BUG-154` on 2026-10-06 while another session's fix took the same number (`completed/BUG-154_environment_banner_can_be_hidden_from_the_toolbar_menu.md`, merged first); this report became `BUG-162`. Its two pictures keep their `BUG-154_` names.
- **Board:** Tools → Options failed from the second open on with "Critical System Error: ... (TradingSettingsView) already deleted". Cause: every page builds its widget once and the shell keeps the page, but the Engine deletes the Options dialog on close and the dialog deletes the page widgets it holds. Fix: `OptionsShell.show_options()` (`src/presentation/ui/options_shell.py`) takes each page's widget back as the dialog finishes, and `OptionsSectionPresenter` connects its change signals once instead of disconnecting a deleted dialog's listener.
- **Context:** Change a setting (Tools → Options, `EPIC-033E`) → `shell/` and the Engine's `WorkbenchShell` / `OptionsDialog` → the Trading options page (`TradingSettingsView`, `src/modules/trading/ui/settings/`), `ui/` layer
- **Environment:** Windows (the user's desktop; paths under `C:\Users\hoang\Documents\Gemini\Sagittarius_Elite_Warrior\.venv`). App commit, engine commit and Python version not captured. The window title reads "Sagittarius Elite Warrior — Trading is OFF. Data view only."; the Market mode was shown, Futures market, BTCUSDT 1m.

## Reproduction
1. Start the app. It was in the Market mode, Futures market, BTCUSDT, with trading off.
2. Choose Tools → Options.

**Expected:** the Options dialog opens on its sections (Tools → Options, `EPIC-033E`).
**Actual:** a "Critical System Error" dialog: "An unexpected error occurred in the UI layer. libshiboken: Internal C++ object (TradingSettingsView) already deleted." No Options dialog opens.

**Frequency:** Not yet established (one occurrence reported). Whether it happens on the first opening of Options in a run, or only after an earlier opening, was not recorded. Not yet reproduced here.

## Symptom
- The user's words: "Khi chọn tool option" (when choosing Tools → Options).
- The error dialog over the Market mode: [`BUG-154_options_error_dialog.webp`](BUG-154_options_error_dialog.webp).
- The Tools menu as shown before choosing it: Options, Indicator parameters… (disabled), Check connection: [`BUG-154_tools_menu.png`](BUG-154_tools_menu.png).
- The traceback, as pasted:

```text
Traceback (most recent call last):
  File "C:\Users\hoang\Documents\Gemini\Sagittarius_Elite_Warrior\.venv\Lib\site-packages\sagittarius_engine\extensions\pyside_mvc\workbench\action_registry.py", line 343, in _run
    entry.handler(checked)
    ~~~~~~~~~~~~~^^^^^^^^^
  File "C:\Users\hoang\Documents\Gemini\Sagittarius_Elite_Warrior\.venv\Lib\site-packages\sagittarius_engine\extensions\pyside_mvc\workbench\workbench_shell.py", line 322, in _on_options
    self.show_options()
    ~~~~~~~~~~~~~~~~~^^
  File "C:\Users\hoang\Documents\Gemini\Sagittarius_Elite_Warrior\.venv\Lib\site-packages\sagittarius_engine\extensions\pyside_mvc\workbench\workbench_shell.py", line 344, in show_options
    dialog = OptionsDialog(self._options_pages, self)
  File "C:\Users\hoang\Documents\Gemini\Sagittarius_Elite_Warrior\.venv\Lib\site-packages\sagittarius_engine\extensions\pyside_mvc\workbench\options_dialog.py", line 51, in __init__
    self._stack.addWidget(page.widget())
    ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
RuntimeError: libshiboken: Internal C++ object (TradingSettingsView) already deleted.
```

## Root cause
The user's traceback is the second or later opening of Tools → Options in a run, not the first; reproduced headless by opening it twice on the real `MainWindow` with the real pages (the first run of `test_tools_options_opens_again_after_it_was_closed` failed with the report's exact `RuntimeError`).
- The three pages (Trading, Market Data, Developer) build their widget once, and `IOptionsPage.widget()` promises "built once". The shell keeps the page across opens (`WorkbenchShell._options_pages`).
- `OptionsDialog.__init__` adds `page.widget()` to its `QStackedWidget` (engine `options_dialog.py:51`), which reparents it into the dialog. `WorkbenchShell.show_options()` (`workbench_shell.py:344-347`) sets `WA_DeleteOnClose`, so closing the dialog deletes it and, with it, every page widget.
- The next `show_options()` calls `page.widget()` on a Python wrapper of a deleted C++ object: `already deleted`. Every page is affected, not only Trading: the Developer page failed the same way.
- A second defect behind the first: `OptionsSectionPresenter.set_change_listener` (`src/support/ui_kit/options_section_presenter.py`) disconnected the previous dialog's listener, a bound method of a dialog Qt had already deleted, which raises `SystemError` once the first defect is out of the way.

## Fix
`src/presentation/ui/options_shell.py`: `OptionsShell(WorkbenchShell)` overrides `show_options()` and, on the dialog's `finished`, orphans every page widget (`setParent(None)`) before the deletion runs, so the widgets outlive the dialog. `MainWindow` derives from it (the `add_options_page` log line moved with it, same logger name). `OptionsSectionPresenter` now connects its change signals once to `_notify_listener`, and a new dialog only replaces who is told.
The cleaner home is the Engine (`show_options` should not let the dialog delete widgets it does not own); that is an Engine change, not made here.

## Regression test
`tests/integration/presentation/ui/test_options_pages.py::test_tools_options_opens_again_after_it_was_closed`: the real `MainWindow` with the real pages, Tools → Options opened and closed twice. Red before the fix with the report's `RuntimeError`, green after.

## Verification
The test above red before and green after; the commit tier (`ci-local.ps1 -SkipTests`) PASS; `tests/unit/architecture` and `test_options_pages.py` green. Positive proof the new mechanism ran: the second open builds a dialog over the same page objects and closes cleanly.
