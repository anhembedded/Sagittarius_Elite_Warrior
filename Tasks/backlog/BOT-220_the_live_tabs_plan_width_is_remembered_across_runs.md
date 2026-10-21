# BOT-220 — The Live tab's Plan width is remembered across runs

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** The Plan used to keep its width through the Bots surface's saved layout; as a pane of the Live tab (BOT-218) its width resets on every launch, and a person who dragged it wide has to do it again.
**Source:** the independent review of PR #673, round 1, 2026-10-21: "the Plan pane's width now resets on every launch".
**Risk:** 🟢 — a remembered number, with a default
**Complexity:** S — one value kept through the existing `UiStateCoordinator`
**Epic (optional):** [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** [BOT-218](../completed/BOT-218_one_plan_column_on_the_live_and_backtest_tabs.md)

---

## 1. Context and problem
`BotsView.live` (`bots_view.py`, splitter `splitBotsLive`) is a plain `QSplitter`, so its sizes are outside the saved perspective the surface keeps (`saveState`), which kept the old Plan dock's width. The same holds for the Backtest tab's splitter (`BacktestWorkbenchView`'s body).

## 2. Acceptance criteria
- [ ] The Live and the Backtest splitters' sizes are saved when the window closes and restored at start, and a saved size that no longer fits the window falls back to the default.
- [ ] A first run, with nothing saved, looks as it does now.

## 3. Design
To be filled: the existing `UiStateCoordinator` contributor pattern (`support/ui_kit/state/`), a `StateScope` of the Bots mode, `QSplitter.saveState`.

## 3a. Reuse
`UiStateCoordinator` (catalog row: "Remember a screen's UI state across runs").

## 4. Changes, per file
To be filled.

## 5. Testing
To be filled.

## 6. Docs touched
To be filled.
