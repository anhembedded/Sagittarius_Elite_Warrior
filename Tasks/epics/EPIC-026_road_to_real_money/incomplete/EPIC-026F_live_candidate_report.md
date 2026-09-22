# EPIC-026F — The candidate report: one strategy, one symbol, one timeframe, judged against the fixed thresholds

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §2 success criterion 2; the user
(2026-09-20): *"hãy cho lô trình để có thể giao dịch thật"*.
**Risk:** 🟡 — a report; the risk is a wrong verdict, which the gate then trusts.
**Complexity:** M — runs, not code: the walk-forward from `EPIC-026E`, the TradingView diff from
`EPIC-001B`, one document that the gate reads.
**Epic:** [`EPIC-026`](../README.md)
**Depends on:** [`EPIC-026E`](EPIC-026E_rolling_walk_forward_validation.md);
[`EPIC-001B`](../../EPIC-001_ema_trend_pullback_tradingview_cross_reference/incomplete/EPIC-001B_run_and_diff_tradingview_vs_app_trade_lists.md)
(the user's run; without it the engine's numbers are unverified against their source).

---

## 1. Context and problem

Six strategies exist (`src/modules/strategy/domain/strategies/`); none has ever been judged
against a written pass mark, and the one with a golden reference (`EmaTrendPullbackStrategy`,
`BOT-109`/`BOT-110`) has not been diffed against that reference. Gate 1 is a document that says
which strategy, which symbol, which timeframe, which parameters, and shows the judge's verdict
per window. Without it, stage 3 opens mainnet for a strategy nobody has measured.

## 2. Acceptance criteria

- [ ] `Tasks/reports/live_candidate/{date}_{strategy}_{symbol}_{timeframe}.md` exists with: the
      exact parameters, the data range and its source (`scripts/epic021c`-style provenance: which
      venue's klines, synced when), the walk-forward table from `EPIC-026E` with the JSON attached
      beside it, the `CandidateVerdict`, and the `EPIC-001B` result (match, or every difference
      explained or filed as a bug).
- [ ] The verdict is **computed** by `LiveCandidateThresholds.judge()`; the report quotes it and
      does not restate it in different words.
- [ ] A failed verdict is a valid outcome of this task: the report says so, names the failing
      threshold, and the gate stays closed. This task is Done when the report exists, not when
      the strategy passes.
- [ ] The chosen symbol and timeframe are the ones `EPIC-026O`'s soak and stage 4 will use, and
      the report says so — one candidate, carried through.

## 3. Design

No new code. The report is written from the `walk-forward --report` JSON and the `EPIC-001B` file.
If the diff in `EPIC-001B` opens a bug, this task waits for the fix and re-runs; a report on a
strategy with a known open bug is not a candidate report. The candidate is the reference strategy
unless the user names another (a user decision, recorded in the report's header).

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `Tasks/reports/live_candidate/{date}_….md` and `.json` | New |
| `Tasks/epics/EPIC-026_road_to_real_money/README.md` | §4 stage 1 row: evidence linked, verdict quoted |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Verdict computed | the JSON's `verdict` block equals the report's | manual | identical |
| Reference diff | `EPIC-001B` in `completed/` with its result section filled | human | linked |
| Documentation guards | `python3 scripts/check_skill_prompt_references.py` | doc | clean |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
