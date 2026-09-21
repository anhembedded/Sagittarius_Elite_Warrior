# EPIC-026E — Rolling walk-forward validation over stored history, on the existing out-of-sample split

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.1; the user (2026-09-20): *"hãy cho lô
trình để có thể giao dịch thật"*.
**Risk:** 🟡 — new application code in `backtesting`; the static engine is reused unchanged, so a
wrong window is a wrong verdict, not a wrong trade.
**Complexity:** M — the split exists (`out_of_sample_split.py`); rolling it and aggregating verdicts
per window is new, and the CLI report is the deliverable.
**Epic:** [`EPIC-026`](../README.md)
**Depends on:** [`EPIC-026D`](EPIC-026D_edge_thresholds_decision.md) (the judge)

---

## 1. Context and problem

`BOT-080` delivered one in-sample/out-of-sample split
(`src/modules/backtesting/domain/out_of_sample_split.py`,
`contracts/out_of_sample_validation.py`). One split answers "did this period generalise once";
a live candidate needs "does it generalise across regimes", which is the rolling (anchored or
sliding) walk-forward every strategy-validation reference names. `grep -ri "walk.forward" src/`
finds nothing. `BOT-107A` in the backlog describes blind OOS testing on the UI; this task is the
headless, report-producing half that stage 1 needs, and `BOT-107A` can consume it later.

## 2. Acceptance criteria

- [ ] `RunWalkForwardCommand(symbol, timeframe, strategy_key, params, window, step, anchored)` runs
      the static backtest per window and returns a `WalkForwardResult` with one `BacktestMetrics`
      per out-of-sample window and the aggregate the judge needs.
- [ ] `main.py walk-forward --symbol … --timeframe … --strategy … --window 90d --step 30d` prints a
      table per window and the `CandidateVerdict` from `EPIC-026D`, and writes the same as JSON
      under `Tasks/reports/walk_forward/` when `--report` is given.
- [ ] Fees and slippage come from the same broker-simulation configuration the UI uses
      (`BOT-104`), never a second default.
- [ ] A window with fewer than the judge's minimum trades is reported as "insufficient", not as a
      pass.
- [ ] Runtime for 1 year of 1h candles and 12 windows is under 60 s on the CI runner (measured;
      the golden-master dataset from `EPIC-025A` PR 0.1 is the fixture).

## 3. Design

A command handler in `modules/backtesting/application/run_walk_forward/` that composes the
existing `RunStaticBacktestCommandHandler` per window — no new engine, no threading (the CLI is
headless; the UI can add a coordinator later). Windows are pure domain: `walk_forward_windows(
start, end, window, step, anchored) -> tuple[Window, ...]` beside `out_of_sample_split.py`, with
the boundary rule (last partial window dropped) tested explicitly. The judge from `EPIC-026D` is
applied per window and to the aggregate; the result DTO is frozen and lives in `contracts/`.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/backtesting/domain/walk_forward_windows.py` | New pure function |
| `src/modules/backtesting/application/run_walk_forward/{command,handler}.py` | New |
| `src/modules/backtesting/contracts/walk_forward_result.py` | New frozen DTO |
| `src/modules/backtesting/composition/command_bindings.py` | Register the handler |
| `src/presentation/cli/walk_forward_cmd.py` and the CLI assembly in `shell/` | New sub-command |
| `tests/unit/modules/backtesting/domain/test_walk_forward_windows.py` | Boundaries, anchored vs sliding |
| `tests/unit/modules/backtesting/application/test_run_walk_forward.py` | Composes the static handler; insufficient-window rule |
| `tests/unit/presentation/cli/test_walk_forward_cmd.py` | Table and JSON output |
| `Docs/VOCABULARY/README.md` | Row: **Walk-forward window** |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Windows | unit test above | unit | green; last partial window dropped |
| Handler | unit test above, static handler faked from its interface | unit | one metrics per window; insufficient named |
| CLI | unit test above | unit | table and JSON |
| Runtime | `time .venv/bin/python main.py walk-forward … ` on the golden-master dataset | manual | < 60 s, number recorded here |
| Fast checks and architecture guards | `ruff`, `mypy`, `pytest tests/unit/architecture -q` | static | clean |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
