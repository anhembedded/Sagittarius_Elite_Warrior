# EPIC-040F — The Grid runs on the workbench and its duplicate backtest UI is deleted

**Status:** ✅ Done (2026-10-20)
**Source:** The owner, 2026-10-14: *"Cái này nên là common của mọi bot chứ nhỉ, k riêng gì bot grid"* ("this should be common to every bot, not just the Grid")
**Risk:** 🔴 — deletes about 1,000 lines of working UI that real-money users read; a lost state or figure misleads a decision
**Complexity:** M — mostly deletion and wiring, guarded by 040A
**Epic:** [EPIC-040](../README.md)
**Depends on:** [EPIC-040E](EPIC-040E_live_and_backtest_tabs.md)

---

## 1. Context and problem
After 040D and 040E, the workbench hosts the Grid through its backtester. The old Grid page (`grid_backtest_view.py`, `grid_backtest_presenter.py`, `grid_backtest_coordinator.py`, `grid_backtest.py`, and parts of `grid_backtest_summary.py` and `equity_chart.py`) is then dead weight, and two copies would drift.

## 2. Acceptance criteria
- [x] Only the Grid-specific remainder stays under `ui/kinds/grid/backtest/`:
  - the backtester registration;
  - any Grid-only extra pane, such as level states at the stop, if the workbench's chart overlay does not already show them.

  Everything else is deleted, not deprecated.
- [x] The figures the Grid showed are all present, now in the outcome's figures list and notes: grid profit, unrealised, cycles, maker and taker fees, average cost, stop reason, coarse periods, and the Futures funding and liquidation lines.
- [x] 040A's characterisation tests pass unchanged against the workbench-hosted Grid.
- [x] The 039B oracle and the 039K tests pass unchanged.
- [x] The epic §2 metric is recorded: lines removed against lines added.
- [x] SPEC-014 and the HLD workbench section describe the two tabs. The `bot_backtest.py` docstring recipes name the new seam.

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

## Re-check against master (2026-10-20, `cd121a5`)
The design held: the Grid is hosted by the workbench since `040E`, and nothing built the old page. Re-scopes, each with its reason:
- **Nothing Grid-specific stays in `ui/kinds/grid/backtest/` but two offline fixtures.** The Grid brings its backtester (`GridKindBacktester`, application layer) and its editor (`GridPanel`); the "level states at the stop" pane was not needed, because the neutral overlay already draws the plan's levels with the replay's fills (`result_overlay`). What is left under the folder is `workbench_frames.py` (the owner's frames) and `sample_replays.py` (the Spot and Futures sample replays the frames and the tests read, moved out of the deleted `preview.py` and `preview_frames.py`).
- **The Grid's `kind_panels` registrations for the page are gone**: `_BACKTESTS`, `_BACKTEST_PROFILES`, `backtest_for` and `backtest_supports`, the two comments that said the tab "stays hidden", and `ui/kinds/bot_backtest.py` itself (`BotBacktest`, `BacktestContext`, `BacktestPorts` had no caller). The recipes that file's docstring held moved to `kind_panels.py`'s.
- **Duplicate records: two dropped, three kept.** `DataWindow` and `BacktestProvenance` were field-for-field copies; the Grid result now carries the neutral ones and the mapper passes the provenance through (`_provenance_of` deleted). `BacktestFill` (it carries the ladder level and a market-fill tag), `EquityPoint` (`grid` and `buy_and_hold`, not `bot` and `benchmark`) and `PriceBar` (the fill rule's own bar, with `PriceStep`) are not copies by shape, and unifying them renames fields the `039B` oracle and the `039K` tests assert on, which this task must leave unchanged.
- **The status-line gaps are pinned on the workbench**, not fixed again: a ready page says nothing stale after another bot (`test_a_ready_page_says_nothing_stale`), and a late refusal after a mid-run bot switch is dropped (`test_another_bot_mid_run_also_drops_a_late_refusal`); both came with `040D`.

## Implementation notes
**What shipped.** The Grid's backtest page, presenter, coordinator, summary, equity chart, preview and frames are deleted; the Bots screen shows the Grid's backtest only through the workbench of `040D`/`040E`. `sample_replays.py` keeps the sample results; `workbench_frames.py` imports them.

**The proof moved with the page, nothing was weakened.** Each deleted test is covered by a workbench test of the same behaviour, or was ported:
- `test_grid_backtest.py` (13): the states, run, cancel, another bot, sync and failure tests are in `test_workbench_states.py` and `test_workbench_runs.py`; "figures scroll in their pane and never raise the floor" is the frame fit test at 1024×700.
- `test_grid_backtest_on_futures.py` (5): the brackets, funding and refusal tests are in `test_workbench_runs.py`; the Spot-does-not-wait and the sync-in-the-venue's-market tests are the new `test_workbench_markets.py`.
- `test_grid_backtest_states.py` (12): the frames are `test_workbench_frames.py`, whose "every state the Grid page had" test now names the thirteen states.
- `test_grid_backtest_preview.py` (2): the coarse sample result is `test_grid_figures_on_the_workbench.py`; "the figures pane shows its figures whole beside a wide chart" is `test_the_figures_tab_shows_its_figures_whole_beside_a_wide_chart` (PR #378's regression).
- `test_grid_backtest_summary.py` (14) is `test_grid_figures_on_the_workbench.py`, reading the outcome's figures and notes through `figure_readout(outcome_of(result))`, which is what the Figures tab draws. `test_grid_kind_backtester.py` now asserts the outcome carries `grid_figures(result)` and `grid_notes(result)` whole.
- The `039B` oracle and the `039K` replay tests are untouched and green.

**Review, round 1 (PR #640).** The log-template catalogue still listed the four log calls of the deleted presenter and coordinator, so `gate (Unit)` was red; regenerated with `scripts/render_log_templates.py --write` (my local runs had left out `tests/unit/support/`). The reviewer also found that the Grid page's `finished_anyway` cases, a full answer that ignores Cancel or arrives after another bot was selected, had no workbench equivalent: `test_workbench_late_answers.py` scripts the dispatcher to answer with a full outcome whatever was asked, and both tests go red when the presenter's fence (`invalidate_active`) is removed. The "never raise the floor" check was weaker than the page's; `test_a_result_never_raises_the_floor_of_the_empty_page` compares a result's minimum size with the empty page's again, and goes red when a result pane asks for 900 px (removing the Figures scroll wrapper does not change the floor, because the read-out asks for none, so that wrapper is not what this test guards). Two docstrings that named the deleted page were corrected. The `039K` statement above is exact only as "no assertion changed": `test_run_futures_grid_backtest.py` had its import moved to `sample_replays`.

**Mutation checks (each went red for the right reason, then restored).** The outcome dropping its notes (nine tests); the sync asking for the Spot market on a Futures bot (an assertion on the markets, not a `NameError`); a Spot run waiting for brackets; a Figures pane held to 60 px wide.

**Measured (epic §2).** Production source: 216 lines added, 1,645 deleted (net −1,429); tests: 213 added, 970 deleted. `ui/kinds/grid/backtest/` held about 1,190 lines of page code in 8 files on 2026-10-14 and 1,812 lines in 10 files before this task (with the two frame sets and previews); it holds 552 lines in 3 files now, all of it offline fixtures, and no page code. A second kind adds its backtester and its editor and no page.

**Frames for the owner.** Before (the old Grid page, `cd121a5`) and after (the workbench) for idle ready, running, refused funding, Spot result, Futures result and Futures liquidated.

**Verified / not.** Commit tier, the architecture, bots, presentation and backtesting unit tests (7,458) green. Not verified: the owner's look on Windows; the full `-Full` gate, which is GitHub's run on the head.
