# EPIC-040D — A kind-neutral Backtest workbench: setup, run state and result panes, written once

**Status:** ✅ Done (2026-10-20)
**Source:** The owner, 2026-10-14: *"Cái này nên là common của mọi bot chứ nhỉ"* ("this should be common to every bot")
**Risk:** 🟡 — the largest new UI piece; it must render the Grid without knowing it is the Grid
**Complexity:** L — a presenter trio, a coordinator for the run, four result panes
**Epic:** [EPIC-040](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-040B](EPIC-040B_kind_neutral_backtest_contract.md), [EPIC-040C](EPIC-040C_sandbox_parameters.md)

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
- [x] A `BacktestWorkbench` package holds the MVP trio, the coordinator and a `preview.py`. It contains:
  - **the setup panel:** source bot, the banner "Simulation only. Not checked against your account and never sent to the bot.", the kind's sandbox editor (040C), interval, period, Run / Cancel / Sync candles / Run without funding, Reset to bot's plan, and the changed-fields line;
  - **the results:** the replay chart drawn by the existing `BotChart` with the kind's `IBotKind.overlay` plus the outcome's fills, the equity against benchmark, the figures read-out, the notes, and a trades table.
- [x] The package imports no `domain/grid` or `ui/kinds/grid` module (040B's guard extended).
- [x] The run follows `async-ui-action-rule.md`:
  - off the UI thread;
  - fenced, so a newer run supersedes an older one;
  - cooperative cancel;
  - a different selection cancels a run in flight and clears the result.
- [x] Every state 040A pinned exists here, with the same words, run through the workbench with the Grid registered.
- [x] Stock widgets only, with no fixed sizes. Usable at 1024×700. The conformance suite passes.

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

**From `040B` (review of PR #627).** The outcome's `figures` carry a `FigureTone` that the workbench maps to the meaning colours (`Tone`); the Grid sets none. The neutral dispatching query (`RunBacktestQuery`: kind id and request in, `BacktestAnswer` out, resolving `IBotKind.backtester()` from the catalog) is written here, where its first caller is. The trades pane pairs the labelled `fills`, since the outcome has no trade record.

**From `040C` (review of the design, 2026-10-20).** The sandbox model exists: `SandboxPlan`, `SandboxSession` (`ui/backtest/`), `judge_sandbox` and `sandbox_line`. The workbench binds its question ("discard your edits?") to `SandboxSession.confirm_switch` / `keep_current`. A second `BotKindPanel` for the sandbox must not be bound to the Bots menu's kind commands (`kind_command_binding.py` acts on the selected bot's panel), and takes `set_plan_facts(None, risk)`. The planner market read the sandbox reuses also reads the account's fee tier and the open orders on the symbol (not the balance); a terms-only read is the narrower option. The workbench says whose fees a run charges. On a position venue it passes the symbol's risk facts to `judge_sandbox`; without them the sandbox answers `LIQUIDATION_FACTS_NOT_READ` and the workbench should show that line rather than hide it.

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

## Re-check against master (2026-10-20, `dd3897f`)
The design held; the re-scopes, each with its reason:
- **Package name.** `ui/backtest_workbench/`, not `ui/backtest/`: `ui/backtest/` already holds 040C's sandbox core, which a guard (`test_sandbox_sends_no_command.py`) keeps to an exact import list, and the workbench must import more (the dispatcher, the run query).
- **No simulated-capital field.** A kind's capital is a parameter of its own editor (the Grid's `capital_quote`); a second field in the workbench would be two answers to one question. The editor's field is the capital.
- **No `extra_panes()` yet.** No kind has an extra pane today; the seam is the editor, the backtester and `BacktestOutcome.detail` (opaque), and a second kind that needs a pane adds one (P7). `bot_backtest.py` says so.
- **Tones not drawn.** `FigureTone` is carried by the outcome but the read-out form has no sanctioned value painting (`ui-presentation-rule.md` §1); it stays data until a figure's meaning needs a colour, and no kind sets one.
- **Trades pane is a fills table.** The outcome has no trade record (040B), so the pane lists the labelled fills; pairing is 040G's.
- **Hosting.** The workbench is a `QWidget` built from `WorkbenchPorts`; `EPIC-040E` puts it in the Bots screen's Backtest tab and `EPIC-040F` deletes the Grid's own page. The conformance suite runs on a booted shell, so its three sizes are 040E's; this task proves the page fits 1024×700 by its minimum size hint (`test_workbench_frames.py`).
- **Frames.** `ui/kinds/grid/backtest/workbench_frames.py` has the fifteen frames (040A's thirteen under the same names, plus an edited sandbox and the discard question), and `ui/backtest_workbench/preview.py` is the neutral sample.

## Implementation notes
**What shipped.** `RunBacktestQuery` and its handler (`application/queries/run_backtest/`), which resolve the kind from the catalog and refuse an unknown kind or a kind with no backtest in words. The workbench package `ui/backtest_workbench/`:
- the run FSM (`backtest_run_fsm_matrix.py`: idle, running, syncing), one fence for both kinds of action, a coordinator off the UI thread, and a presenter that builds one `WorkbenchState` the view only applies;
- `SandboxEditing`, which holds 040C's session, a second editor instance per kind (never bound to the Bots menu) and the kind's own verdicts with no account;
- the panes: replay chart (`BotChart` with the kind's overlay and the outcome's fills), equity, figures, notes, fills table.

The page says the Grid page's words in every state 040A pinned (`test_workbench_states.py` runs them with the Grid registered as the only kind) and fixes the three status-line gaps 040A found (a ready page says nothing stale; "Backtest done." and "Backtesting…" go with the selection). It says whose fees a run charges. A stub strategy kind renders through it with no Grid in the process (`test_workbench_with_another_kind.py`).

**Guards.** `test_backtest_outcome_is_kind_neutral.py` now scans the workbench package too (the editor's base class, `bot_kind_panel`, is named as shared by kinds); `test_backtest_workbench_reaches_no_order_or_account.py` is an allow-list over the money-adjacent import families plus a check that the only thing dispatched is `RunBacktestQuery`. An integration test resolves the query as the dispatcher does, on the real module.

**Mutation checks (each went red, then restored).** The stale-answer fence removed; the request built from the bot's config instead of the sandbox's; the refused-plan guard in the presenter; funding `OPTIONAL` for `REQUIRED`; the sync-stopped wording; the discard question not disabling the editor; the editor not showing the copy; a fill's side swapped; the overlay drawn without the replay's first price; the brackets gate; the query's binding removed.

**Review, round 1 (PR #631).** The review found the sandbox judged and replayed with the *selected* bot's market numbers after "keep my edits" (a wrong simulation that looked right); Cancel with nothing running raising from a Qt slot; two of 040A's states unpinned (the funding refusal's sentence, the liquidation notes); the re-run after a sync always demanding funding; a guard that covered imports but not the authority the package held (a full dispatcher, `executor_factory`); two over-long signatures; and an untyped sync sentinel. Fixed: the sandbox keeps the market and risk facts of its source bot (`SandboxEditing.copies`), so a kept sandbox is judged and replayed with its own bot's numbers and a run in flight finishes for it; Cancel is a no-op unless something runs; both states are pinned; the re-run keeps the funding the person chose; the workbench is handed `run_query`, a function of the one query, instead of a dispatcher, and the guard bans `.dispatch`, `executor_factory`, `recovery_layer` and widens its sensitive families; `OutcomeShown` and `KindSources` replace the long signatures; `Synced` is a typed answer and an unknown answer is logged and shown as a failed run. Round 2 (BOT-205 merged in): the replay chart follows the shared display time zone (`WorkbenchPorts.display_timezone`), pinned by a test.

**Verified / not.** Commit tier, the architecture suite, the workbench unit tests and the integration test green. Not verified: the page is not on screen in the app (040E), so no Windows look beyond the frames and no conformance run.
