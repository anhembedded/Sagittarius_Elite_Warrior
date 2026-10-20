# EPIC-040B — One kind-neutral backtest result and simulator port; the Grid's replay answers through it

**Status:** ✅ Done (2026-10-20)
**Source:** The owner, 2026-10-14: *"Cái này nên là common của mọi bot chứ nhỉ, k riêng gì bot grid"* ("this should be common to every bot, not just the Grid")
**Risk:** 🟡 — a new contract every later task builds on; a wrong shape is paid for by every kind
**Complexity:** M — a contract, a port, an adapter around existing code, no simulator change
**Epic:** [EPIC-040](../README.md)
**Depends on:** [EPIC-040A](EPIC-040A_pin_grid_backtest_behaviour.md)

---

## 1. Context and problem
- The only backtest result type is `GridBacktestResult` (`domain/grid/grid_backtest_result.py:122`). It carries Grid concepts (`plan`, `final_states`, `completed_cycles`, `grid_profit`) next to kind-neutral ones (`bars`, `equity`, `fills`, fees, `provenance`, stop reason, caveats).
- The only query is `RunGridBacktestQuery` (`application/queries/run_grid_backtest/query.py:30`).
- A second kind would have to invent its own result, and the UI would branch on it.

## 2. Acceptance criteria
- [ ] A kind-neutral `BacktestOutcome` holds:
  - provenance, bars, the equity curve, the benchmark curve, fills, fees;
  - the stop reason and its detail;
  - **figures**: an ordered list of labelled values with a tone;
  - **notes**: caveat sentences;
  - **detail**: one kind-specific object the kind's own code reads.
- [ ] An `IKindBacktester` port (application contracts) runs one kind's replay: `run(request, cancelled) -> BacktestOutcome | BacktestRefusal | BacktestCancelled`. Its request carries:
  - symbol, venue, config, terms, interval and period;
  - the optional position-venue facts that exist today (brackets, funding requirement).
- [ ] The Grid's adapter implements the port by calling the existing `RunGridBacktestQuery` handler and mapping `GridBacktestResult` into the outcome. The `GridBacktestResult` stays as the `detail`.
- [ ] The port is found by kind id through the existing kind registry (`kind_panels` / `IBotKindCatalog`). Nothing outside the Grid names the Grid.
- [ ] The 039B oracle and the 039K tests pass unchanged; the figures are byte-identical.
- [ ] An architecture guard forbids kind-neutral code from importing `domain/grid`.
- [ ] The request and outcome also fit the strategy kind of [EPIC-040G](../incomplete/EPIC-040G_strategy_bot_kind.md), proven by a test stub adapter, not by a real strategy:
  - the request can ask for warm-up history before the period;
  - the outcome's trades can be one position at a time, entered and exited, not only ladder fills.

## 3. Design
**Envelope plus detail.** This is the same shape `FuturesOutcome` already uses inside `GridBacktestResult` (`EPIC-039K`): common fields every pane reads, plus one opaque kind object that only the kind's own panes read. P5: reuse the pattern the codebase already has.

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Envelope + kind `detail` (chosen) | The workbench draws equity, figures, notes and trades with no kind knowledge. The kind keeps its rich object for its own extras. |
| A generic `dict` result | Rejected: untyped seams (`code/quality.md`, zero `Any` at seams). |
| A base class that each kind's result inherits | Rejected: inheritance couples every kind to one hierarchy, and the mapping is the honest boundary. |
| Make the Grid result the common type | Rejected: it leaks `plan` and `cycles` into kinds that have neither. |

**Figures as data, not fields.** "Return", "Max drawdown", "Grid cycles" and "Funding" are a list the kind fills. The workbench renders any list, so a new kind's metrics need no UI change. Tones use the existing `Tone` enum (`meaning_colours.py`).

**Risks:**
- Under-specifying the envelope pushes kind code back into the workbench. Mitigation: 040D's acceptance criteria require the workbench to render the Grid without importing it.
- Mapping the Futures funding and liquidation lines into figures and notes must not drop the "FUNDING IS NOT INCLUDED" first note. Pinned by 040A.

## 3a. Reuse
- **Result shape:** the `FuturesOutcome` envelope pattern; `RunGridBacktestQuery` and its handler, unchanged; `ColumnKind` stays in the UI (the neutral `FigureKind` maps to it), because the contracts and the domain import no Engine type.
- **Kind lookup:** the existing kind seam. `IBotKind.backtester()` is concrete and `None` by default, like `recovery_layer`, so no implementer changes (`BUG-026`); `GridKind` is *given* its adapter where it is built, as it is given its executor factory. No second registry.
- **Held thread pool, scripted dispatcher:** none needed; the tests use real collaborators and a scripted `IQueryHandler`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/backtest/backtest_outcome.py` | New: `BacktestOutcome`, `BacktestFigure`, `FigureKind`, `FigureTone`, and the records it holds (`BacktestBar`, `EquityPoint`, `BacktestFill`, `BacktestProvenance`, `DataWindow`) |
| `src/modules/bots/domain/backtest/backtest_answer.py` | New: `BacktestRefusal`, `BacktestCancelled`, `BacktestAnswer` |
| `src/modules/bots/domain/backtest/funding_requirement.py` | Moved from `application/queries/run_grid_backtest/` (the request, in `contracts`, may not import `application`); five importers retargeted |
| `src/modules/bots/contracts/i_kind_backtester.py` | New: `IKindBacktester`, `KindBacktestRequest` (with `warmup`) |
| `src/modules/bots/contracts/i_bot_kind.py` | `backtester()`, concrete, `None` |
| `src/modules/bots/domain/grid/grid_kind.py` | Takes an optional backtester and answers it |
| `src/modules/bots/domain/grid/grid_figures.py` | New: the Grid's figures and notes, moved out of the page's summary |
| `src/modules/bots/ui/kinds/grid/backtest/grid_backtest_summary.py` | `summary_of` builds its read-out from `grid_figures`/`grid_notes` (same keys, titles, kinds, values) |
| `src/modules/bots/application/kinds/grid/grid_kind_backtester.py` | New: the adapter over the existing handler, and `outcome_of` |
| `src/modules/bots/composition/executor_bindings.py` | `_build_kind_catalog` gives `GridKind` its adapter |
| `tests/unit/architecture/test_backtest_outcome_is_kind_neutral.py` | New guard |
| `Docs/MODULES/bots/` | `05-building-blocks.md`, `05-kind-seam.puml`, `03-context.md`, `README.md` |

## 5. Testing
Unit tests for the mapping over the oracle's own 80 replays; the funding note first; refusal and cancellation flags; the real handler over stored and empty fakes; a stub strategy adapter; the architecture guard and its probe; a wiring test on the real module. The 039B oracle and the 039K suites run with their assertions unchanged.

## Re-check against master (2026-10-20, `e6551b2`)
The design held, with four re-scopes, each decided by the constraints and recorded here:
- **The neutral types are defined in `domain/backtest/`, not in `contracts/backtest_outcome.py`.** The Grid's figures are built by a domain function (`grid_figures.py`), and a domain file builds `BacktestFigure`, so the records it builds must be importable from the domain. (`domain → contracts` is not forbidden here: seventeen domain files of this module import `bots.contracts` already.) Only the port, which the kind seam `IBotKind` names, sits in `contracts`. The simulator does not return the neutral cancelled value: the adapter maps `GridBacktestCancelled`.
- **Mapping, not moving.** `PriceBar`, `EquityPoint`, `BacktestFill` and the provenance are Grid-module types the 039B oracle and the 039K tests import. Moving them would retarget those tests. So the outcome holds its own small records and the adapter maps (`PriceBar`→`BacktestBar`, `EquityPoint.grid`→`bot`, `BacktestFill.level_index` stays in `detail`). `040F` can drop the Grid copies once the page reads the outcome.
- **`FundingRequirement` moved to the domain.** The request carries it and a contract may not import `application`. Two 039J/039K test files changed an import line, nothing else.
- **No new query or registry.** The task's "found by kind id through the registry" is `IBotKind.backtester()` on the catalog's kind. The neutral query that dispatches it is `040D`'s, where its first caller is.
- **The stop reason is in the outcome** (`stop: StopCause`, `stop_detail`), as the original acceptance list asked; a first draft left it as prose only, and review caught it. The workbench can mark a liquidation or a stop loss on the chart without reading English.
- **Figures are `FigureKind`, not the Engine's `ColumnKind`, and tones are a neutral enum.** The Grid sets none today (its page shows none); `040D` maps `FigureTone` to the meaning colours.

## Implementation notes
**What shipped.** The kind-neutral outcome, answer and request; the `IKindBacktester` port, found through `IBotKind.backtester()`; the Grid's adapter over the existing handler, with its figures and notes written once in `grid_figures.py` and read by both the adapter and the page's summary (so the two cannot drift until `040F`); the composition giving `GridKind` its adapter; the guard. No simulator, handler or page behaviour changed.

**Fitting the strategy kind.** The request has `warmup` (history before the period a kind may want to prime itself; the Grid ignores it), and a one-position-at-a-time kind reports each entry and exit as a labelled fill, which the stub-adapter test proves without a strategy. `040G` may add a `trades` list if a position record is wanted; the seam is the fills list.

**Mutation checks (each went red, then restored).** A fill label dropped (75 cases); the request's brackets dropped; the window's two counts swapped; the stop cause fixed (the three the first review proved the tests missed); the funding note moved off first (1); the composition not giving the Grid its adapter (the wiring test); a refusal's flags dropped (2); the equity curve's two sides swapped (80); a Grid import added to the outcome (the guard).

**Follow-ups, each recorded in the file of the task that does it:** `040D` — map `FigureTone` to the meaning colours, write the neutral dispatching query, build the trades pane from the labelled fills; `040F` — drop the Grid's duplicate records (`PriceBar`, `EquityPoint`, `BacktestFill`, `BacktestProvenance`, `DataWindow`) once the oracle's imports are retargeted; `040G` — a trade record beside `fills`, or the workbench pairs entries and exits, and the assertion that nothing before `start` is reported (the stub test here cannot make it).

**Findings for `040D`/`040F`, not fixed here.** `FigureKind` has four kinds, the ones the Grid uses; a kind with a text or a duration figure adds a member and its mapping. `BacktestBar` repeats `PriceBar`'s five fields; `040F` can merge them when the oracle's import is retargeted.

**Verified / not.** Commit tier, the architecture suite, `tests/unit/modules/bots` and the wiring test green. Not verified: nothing draws the outcome, so no screen shows it yet.
