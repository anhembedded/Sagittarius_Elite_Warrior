# EPIC-040B — One kind-neutral backtest result and simulator port; the Grid's replay answers through it

**Status:** 🔵 Backlog
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
- [ ] The request and outcome also fit the strategy kind of [EPIC-040G](EPIC-040G_strategy_bot_kind.md), proven by a test stub adapter, not by a real strategy:
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
- **Result shape:** used the `FuturesOutcome` envelope pattern, `Tone`, `RunGridBacktestQuery` and its handler, unchanged.
- **Kind lookup:** used the existing kind registry rather than a new one.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/backtest_outcome.py` | New: `BacktestOutcome`, `BacktestFigure`, `BacktestRefusal`, `BacktestCancelled` |
| `src/modules/bots/contracts/i_kind_backtester.py` | New port and request |
| `src/modules/bots/application/services/grid_kind_backtester.py` | Grid adapter over the existing handler |
| kind registration (`kind_panels.py` or the catalog) | Registers the adapter by kind id |
| `tests/unit/architecture/...` | Guard: kind-neutral code imports no `domain/grid` |

## 5. Testing
- Unit tests for the mapping: every `GridBacktestResult` field lands somewhere; the funding note comes first.
- The oracle and the 039K suites run unchanged.
- An architecture guard probe.
- The commit tier.
