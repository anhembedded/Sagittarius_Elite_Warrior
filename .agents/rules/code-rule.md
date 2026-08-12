---
trigger: always_on
---

# Development Guidelines

- **No Hardcoding**: Avoid magic strings, magic numbers, or hardcoded configurations. Always refer to existing related implementations, established enums, or central configuration files (`config_keys.py`, `user_config.json`, etc.).
- **Strictly Follow SOLID Principles**: Ensure any new features, refactors, or code additions adhere strictly to SOLID principles:
  - **S**ingle Responsibility Principle (SRP)
  - **O**pen/Closed Principle (OCP)
  - **L**iskov Substitution Principle (LSP)
  - **I**nterface Segregation Principle (ISP)
  - **D**ependency Inversion Principle (DIP)
- **No Lazy Code**: Don't take the shortcut that's easiest to type over the one that's easiest to read/maintain.
  - Split by responsibility into separate files/modules instead of piling unrelated logic into one file or one function.
  - Model data with proper structures — dataclasses, value objects, `Enum` — instead of loose primitives, dicts, or magic strings/tuples standing in for a real type.
  - Do not use `lambda`. Write a named function/method instead — it gets a real name, can carry a docstring, and shows up properly in stack traces/coverage/debuggers.
- **Every new feature/screen ships with sanity tests**, in `tests/sanity/`, alongside its unit tests — not a follow-up, part of the same task. Two kinds, both construction-only (see example: `tests/sanity/test_backtest_screen_di_sanity.py` + `test_backtest_screen_ui_sanity.py`):
  - **Sanity (DI)**: boot the real app (`create_app()`, no mocked dispatch) and assert every command/query the feature dispatches resolves to its real handler via `container.resolve(command_class)`, and every registry it depends on (`StrategyRegistry`, `IndicatorScriptRegistry`, etc.) has the keys it expects. Catches a dropped/renamed DI registration before any behavior test even runs.
  - **Sanity (UI)**, for screens: construct the real View + Presenter against the real DI container (not a mocked one) and assert it doesn't raise, plus every QML document parses with `quick_widget.errors() == []` (QML parse errors don't raise a Python exception — they only show up there).
  - **Construction-only, always** — no button clicks, no `requestRun()`-style dispatch, no background threads, no network. Real actions belong in `tests/unit/` (mocked dispatch) or `tests/integration/`. Sanity exists to be fast and reliable; the UI integration suite (`tests/integration/presentation/ui/`) has a known intermittent native-crash bug (`BOT-038`) when run as one full block — sanity must never approach that territory.
- **When the user reports a bug, write a regression test that reproduces it before fixing the code.** Diagnose the root cause first, then express that root cause as a failing test (e.g. `test_switching_to_equity_mode_disables_and_hides_the_ema_overlay` for the BOT-056 EMA-overlay-not-hidden bug) — confirm it fails for the right reason, then fix the code until it passes. This turns every reported bug into a permanent regression test, not just a one-off patch — skipping straight to the fix leaves nothing guarding against the same bug coming back.
