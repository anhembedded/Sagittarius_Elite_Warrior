# EPIC-026D — The acceptance thresholds for a live candidate are fixed before any run

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §4 and the ADR's `❓ O1`; the user
(2026-09-20): *"hãy cho lô trình để có thể giao dịch thật"* ("give a roadmap to be able to trade
for real") — the roadmap's first gate is a number the user has to choose.
**Risk:** 🟢 — a decision record and a frozen value object; no behaviour changes.
**Complexity:** S — the work is a conversation and one dataclass; the difficulty is that the
values are a risk-appetite decision the agent may not make.
**Epic:** [`EPIC-026`](../README.md)
**Depends on:** None — this is the user's decision, asked with the context `report-rule.md` §2
requires.

---

## 1. Context and problem

A candidate report (`EPIC-026F`) that chooses its own pass mark after seeing the numbers proves
nothing; `BOT-078` §1.2 recorded exactly that failure mode ("tuning on one period, no split — an
overfitting machine with no brakes"). The thresholds have to be written down, dated and accepted
**before** `EPIC-026E`/`F` run. The repository has the metrics already
(`src/modules/backtesting/contracts/backtest_metrics.py:53-110`: profit factor, Sharpe, Sortino,
Calmar, max drawdown, streaks) and an out-of-sample split; it has no threshold anywhere.

## 2. Acceptance criteria

- [ ] `DECISION_{date}_live_candidate_thresholds.md` exists in this epic from the decision
      template, status Accepted, with the user's values quoted verbatim (🟢 User decision) for at
      least: out-of-sample profit factor minimum, maximum drawdown, minimum trade count, minimum
      fraction of walk-forward windows that must pass, fee model assumed.
- [ ] The ADR's `O1` row is closed with a link to that record.
- [ ] `src/modules/backtesting/contracts/live_candidate_thresholds.py` holds the same values as a
      frozen dataclass with a `judge(metrics) -> CandidateVerdict` that names each failing
      threshold — so `EPIC-026F`'s report is computed, not eyeballed.
- [ ] A unit test pins the dataclass to the decision record's values, so a silent edit of either
      fails.

## 3. Design

The agent's part is to **frame** the decision (`report-rule.md` §2): current metrics of the
reference strategy from its most recent backtest, what the literature treats as minimums, and a
recommended set. The user's part is the numbers. The dataclass lives in `backtesting/contracts`
because the judge reads `BacktestMetrics`; `strategy` does not import it (`backtesting` is
downstream of `strategy`, HLD §2).

Recommended framing to put to the user (not a decision): profit factor ≥ 1.3 out of sample,
maximum drawdown ≤ 15 %, ≥ 100 trades out of sample, ≥ 70 % of rolling windows profitable, fees
0.05 % taker both sides.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `Tasks/epics/EPIC-026_road_to_real_money/DECISION_{date}_live_candidate_thresholds.md` | New; Accepted with the user's values |
| `Tasks/epics/EPIC-026_road_to_real_money/DECISION_2026-09-20_mainnet_venue.md` | `O1` closed |
| `src/modules/backtesting/contracts/live_candidate_thresholds.py` | New frozen dataclass and `judge()` |
| `tests/unit/modules/backtesting/contracts/test_live_candidate_thresholds.py` | Pins values; one test per threshold's failing branch |
| `Docs/VOCABULARY/README.md` | Row: **Live candidate** |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Values pinned | `.venv/bin/python -m pytest tests/unit/modules/backtesting/contracts/test_live_candidate_thresholds.py -q` | unit | green; each failing branch named |
| Fast checks | `.venv/bin/ruff check src tests`, `ruff format --check`, `mypy` on the new file | static | clean |
| Documentation guards | `python3 scripts/check_skill_prompt_references.py` | doc | clean |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
