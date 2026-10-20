# EPIC-040F — The Grid runs on the workbench and its duplicate backtest UI is deleted

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"Cái này nên là common của mọi bot chứ nhỉ, k riêng gì bot grid"* ("this should be common to every bot, not just the Grid")
**Risk:** 🔴 — deletes about 1,000 lines of working UI that real-money users read; a lost state or figure misleads a decision
**Complexity:** M — mostly deletion and wiring, guarded by 040A
**Epic:** [EPIC-040](../README.md)
**Depends on:** [EPIC-040E](../completed/EPIC-040E_live_and_backtest_tabs.md)

---

## 1. Context and problem
After 040D and 040E, the workbench hosts the Grid through its backtester. The old Grid page (`grid_backtest_view.py`, `grid_backtest_presenter.py`, `grid_backtest_coordinator.py`, `grid_backtest.py`, and parts of `grid_backtest_summary.py` and `equity_chart.py`) is then dead weight, and two copies would drift.

## 2. Acceptance criteria
- [ ] Only the Grid-specific remainder stays under `ui/kinds/grid/backtest/`:
  - the backtester registration;
  - any Grid-only extra pane, such as level states at the stop, if the workbench's chart overlay does not already show them.

  Everything else is deleted, not deprecated.
- [ ] The figures the Grid showed are all present, now in the outcome's figures list and notes: grid profit, unrealised, cycles, maker and taker fees, average cost, stop reason, coarse periods, and the Futures funding and liquidation lines.
- [ ] 040A's characterisation tests pass unchanged against the workbench-hosted Grid.
- [ ] The 039B oracle and the 039K tests pass unchanged.
- [ ] The epic §2 metric is recorded: lines removed against lines added.
- [ ] SPEC-014 and the HLD workbench section describe the two tabs. The `bot_backtest.py` docstring recipes name the new seam.

## 3. Design
**Strangler step: delete only once the replacement is proven by the same tests.** 040A wrote the tests before the move, 040D made them pass on the workbench, and this task removes the old path. No feature flag: a flag would keep both copies alive. The safety net is the pinned tests plus the owner's look at the preview frames.

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Delete in one PR after the tests pass on the new path (chosen) | One copy and no drift; the tests prove nothing was lost. |
| Keep the old page behind a toggle for a while | Rejected: two copies of a real-money read-out invite exactly the drift the epic removes. |
| Delete incrementally per pane | Acceptable if the PR grows past review size. Split by pane; each PR still passes the 040A tests. |

**Risks:**
- **A figure silently missing.** Mitigation: 040B's mapping test asserts every `GridBacktestResult` field lands in the outcome, and this task's review compares the before and after preview frames side by side.
- **A Futures-only line lost on Spot or shown on Spot.** Mitigation: 040A pinned both venues.
- **Docs drift.** SPEC-014 and HLD §11 are updated in the same PR.

**From `040B` and `040A` (reviews of PR #624 and #627).** Drop the Grid's duplicate records (`PriceBar`, `EquityPoint`, `BacktestFill`, `BacktestProvenance`, `DataWindow`; `BacktestBar` repeats `PriceBar`) once the 039B oracle's imports are retargeted. Fix the status line (`show_idle("")` writes none: it leaves "Backtest done." after another bot, "Backtesting…" after a mid-run switch, "Select a bot…" once ready) and pin it. A late *refusal* after a mid-run bot switch is not framed in `040A`: add that frame when the fence moves.

## 3a. Reuse
- **Results and workbench:** used `BacktestOutcome` from 040B and the workbench from 040D.
- **New code:** none, because this task deletes and rewires.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/kinds/grid/backtest/*` | Delete the page, presenter, coordinator and moved panes; keep the registration and Grid-only extras |
| `src/modules/bots/ui/kinds/kind_panels.py` | Registration through the new seam. `EPIC-040E` left four symbols with no production caller: `backtest_for`, `backtest_supports`, `_BACKTESTS` and `_BACKTEST_PROFILES`, and two comments that still say the Backtest tab "stays hidden"; delete them here |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/HLD/11_desktop_workbench.md` | The two tabs and the sandbox |
| `Tasks/epics/EPIC-040_backtest_workbench/README.md` | §2 metrics measured |

## 5. Testing
- 040A's tests on the workbench, unchanged.
- The oracle and the 039K suites.
- The full gate (`-Full`).
- Before/after preview frames for the owner.
- A reviewer session: an epic PR gets one by default.
