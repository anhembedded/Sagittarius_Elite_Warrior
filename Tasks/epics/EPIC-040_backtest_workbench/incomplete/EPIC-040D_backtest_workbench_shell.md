# EPIC-040D — A kind-neutral Backtest workbench: setup, run state and result panes, written once

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"Cái này nên là common của mọi bot chứ nhỉ"* ("this should be common to every bot")
**Risk:** 🟡 — the largest new UI piece; it must render the Grid without knowing it is the Grid
**Complexity:** L — a presenter trio, a coordinator for the run, four result panes
**Epic:** [EPIC-040](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-040B](../completed/EPIC-040B_kind_neutral_backtest_contract.md), [EPIC-040C](EPIC-040C_sandbox_parameters.md)

---

## 1. Context and problem
These parts of the Grid's page are not about the Grid:
- the interval and period;
- Run, Cancel and Sync candles;
- the refusal that offers a sync (`BUG-107`);
- the "Run without funding" choice (`EPIC-039K` O9);
- the equity against buy-and-hold;
- the summary read-out;
- the notes.

Today they live under `ui/kinds/grid/backtest/` (`grid_backtest_view.py`, `grid_backtest_presenter.py`, `grid_backtest_coordinator.py`, `equity_chart.py`, `grid_backtest_summary.py`). With 040B's outcome and 040C's sandbox, they can be written once.

## 2. Acceptance criteria
- [ ] A `BacktestWorkbench` package holds the MVP trio, the coordinator and a `preview.py`. It contains:
  - **the setup panel:** source bot, the banner "Simulation only. Not checked against your account and never sent to the bot.", the kind's sandbox editor (040C), simulated capital, interval, period, Run / Cancel / Sync candles / Run without funding, Reset to bot's plan, and the changed-fields line;
  - **the results:** the replay chart drawn by the existing `BotChart` with the kind's `IBotKind.overlay` plus the outcome's fills, the equity against benchmark, the figures read-out, the notes, and a trades table.
- [ ] The package imports no `domain/grid` or `ui/kinds/grid` module (040B's guard extended).
- [ ] The run follows `async-ui-action-rule.md`:
  - off the UI thread;
  - fenced, so a newer run supersedes an older one;
  - cooperative cancel;
  - a different selection cancels a run in flight and clears the result.
- [ ] Every state 040A pinned exists here, with the same words, run through the workbench with the Grid registered.
- [ ] Stock widgets only, with no fixed sizes. Usable at 1024×700. The conformance suite passes.

## 3. Design
**The kind seam stays where `EPIC-029D` put it, with the boundary moved one level down.**
- Today the seam is "a kind returns a whole page" (`BotBacktest.page`), so every kind writes a page.
- After this task the seam is "a kind returns a backtester (040B), an editor (it already does) and optional extra panes". The page is the workbench's.

| | Today (`BotBacktest`) | After |
| :--- | :--- | :--- |
| Who builds the page | each kind | the workbench, once |
| What a kind provides | a page widget | `IKindBacktester` + `BotKindPanel` + optional `extra_panes()` |
| Cost of a new kind's backtest UI | a full page | a registration |

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Workbench owns the page; kinds plug in (chosen) | Removes the duplication the owner flagged. Matches P7 and the existing kind registry. |
| Keep `BotBacktest.page` and share helpers | Rejected: every kind still assembles the page, so the run states drift apart; helpers do not hold an FSM together. |
| A generic page driven by a declarative spec per kind | Over-engineering for one kind today. The plug-in points above are enough; revisit if three kinds disagree. |

**The run state is an explicit FSM** (idle, running, refused with an offer, cancelled, shown), in a `*_fsm_matrix.py`, as the screen's other state machines are (`bots_ui_fsm_matrix.py`).

**Size.** The 400-line ceiling applies. Split by pane (setup, chart, equity, figures, trades), each with its own view model.

**Risks:**
- **Feature loss in the move.** Mitigated by 040A's tests re-run here.
- **Futures-only controls leaking into Spot.** "Run without funding" appears only when the refusal says funding is missing; the venue profile decides, as in 039J.
- **Chart cost.** Reuse `BotChart`; a second drawer is banned by ADR D16.

## 3a. Reuse
- **Charts:** used `BotChart`, `IBotKind.overlay` and the equity chart, moved from `grid/backtest/equity_chart.py`.
- **Read-out:** used `ReadoutForm` (`EPIC-033N`).
- **Async:** used `fenced_reads` and the coordinator pattern from `async-ui-action-rule.md`.
- **Candle sync:** used `IMarketDataSync`.
- **New:** none of the panes is new art; each is moved out of the Grid.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/backtest/` | New package: `backtest_workbench_presenter.py`, `_view.py`, `_view_model.py`, `backtest_run_coordinator.py`, `backtest_run_fsm_matrix.py`, the panes, `preview.py` |
| `src/modules/bots/ui/kinds/bot_backtest.py` | The seam becomes backtester + editor + optional extra panes. The docstring recipes are updated |
| `tests/unit/modules/bots/ui/backtest/` | FSM, fencing, cancel-on-reselect, and 040A's states via the workbench |

## 5. Testing
- Unit tests: the FSM matrix and the presenter with the Grid backtester registered.
- Integration test: a run on the fake exchange's stored candles.
- Conformance suite at three sizes.
- Preview frames for the owner.
- 040A's characterisation tests pointed at the workbench.
