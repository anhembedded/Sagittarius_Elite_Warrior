# BUG-162 — Tools → Options opens a "Critical System Error" instead of the Options dialog

- **Reported:** 2026-10-06 (the user, in chat, with two screenshots and the traceback)
- **Severity:** 🟡 P2 — the Options dialog does not open, so no setting can be changed from the app (Tools → Options is the one place for them, `ui-presentation-rule.md` §7)
- **Status:** Open
- **Renumbered:** filed as `BUG-154` on 2026-10-06 while another session's fix took the same number (`completed/BUG-154_environment_banner_can_be_hidden_from_the_toolbar_menu.md`, merged first); this report became `BUG-162`. Its two pictures keep their `BUG-154_` names.
- **Board:** Tools → Options shows "Critical System Error: libshiboken: Internal C++ object (TradingSettingsView) already deleted." and no Options dialog opens. Seen in the Market mode on the user's desktop. Not investigated yet.
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
Not yet established. The user asked for the report only; no investigation was done.

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Ask, or find out, whether Options was opened earlier in the same run, and record the app and engine commits of the run.
- Reproduce headless by opening Tools → Options on the booted workbench, once and then a second time.
- Then follow `fix-bug-rule.md`.
