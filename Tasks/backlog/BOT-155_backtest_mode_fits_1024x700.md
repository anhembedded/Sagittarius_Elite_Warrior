# BOT-155 — The Backtest mode, and so the window, shrinks to 1024×700

**Status:** 🔵 Backlog
**Source:** the conformance suite's new `fits_the_window` check (`EPIC-033C`, PR #370), and its independent review: "the window's minimum is 1400×727, so every mode is unusable on a 1366×768 laptop screen, not just Backtest"
**Risk:** 🟡 — the chart's display controls move; the marker filters (PROP-004) must keep working
**Complexity:** M — `BacktestChartControls` becomes a toolbar of actions, and its tests follow
**Epic (optional):** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md)
**Depends on:** None

---

## 1. Context and problem
- **Measured on PR #370:** the window cannot be made narrower than 1400 px in any mode, because its minimum size is the largest of its modes'. The Backtest mode needs 1400×688.
- **Cause:** `BacktestChartControls` (`src/modules/backtesting/ui/logic/chart_controls.py`) lays out three radio buttons, three check boxes, two combo boxes and a spin box in one `QHBoxLayout` row about 1027 px wide, above the chart (`backtest_view.py`, `charts_layout.insertWidget(0, …)`). A row of widgets cannot shrink below the sum of its parts.
- **Baseline:** the suite records this as `backtest@1024x700` and `backtest@1366x768` (`fits_the_window`) in `tests/integration/presentation/ui/baseline_workbench_conformance.json`.
- **The other entry has another owner:** `dashboard@1024x700` (the Dev Board's eight-dock rail) is not this task's. EPIC-033P deletes the Dev Board, and that entry goes with it.

## 2. Acceptance criteria
- [ ] The Backtest mode's minimum width lets the window be 1024 px wide. `fits_the_window` passes for `backtest` at every size, and both `backtest@…` baseline entries are removed.
- [ ] Every control keeps its effect: chart mode, strategy indicators, volume and buy/sell flags; the outcome, side and minimum-|PnL| marker filters; Spot hiding "Short only"; Equity mode disabling the flags and filters.
- [ ] The conformance checks `toolbar_actions_only` and `no_button_duplicates_a_command` still pass.

## 3. Design
Use a `QToolBar` above the chart, as the chart's own `ChartToolbar` already does. It overflows into its extension button when narrow (Qt `QToolBar`, MS `cmd-toolbars`).
- **Chart mode:** checkable `QAction`s in an exclusive `QActionGroup`, so the state is not held in radio buttons (`ui-presentation-rule.md` §6).
- **The three layers:** checkable actions.
- **The two filters and the threshold:** `QWidgetAction`s, which the toolbar check accepts.
- **Signals stay as they are:** `BackTestView` reads the same signals and getters it reads today.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/backtesting/ui/logic/chart_controls.py` | a toolbar of actions in place of the row of widgets |
| `src/modules/backtesting/ui/backtest_view.py` | inserts the toolbar where the row was |
| `tests/unit/modules/backtesting/ui/…chart_controls…` | drive the actions instead of the buttons |
| `tests/integration/presentation/ui/baseline_workbench_conformance.json` | remove both `backtest@…` entries |

## 5. Testing
- **Unit:** each action and filter emits what the old control did. Spot removes "Short only"; Equity disables the flags and the filters.
- **Integration:** `test_workbench_conformance.py` at all three sizes, with the `backtest` entries gone from its baseline.
