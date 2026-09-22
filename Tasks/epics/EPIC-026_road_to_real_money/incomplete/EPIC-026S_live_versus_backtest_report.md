# EPIC-026S — After each real-money capital stage, a live-versus-backtest report; the next increase is a user decision

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §2 success criterion 5, §4 stage 4; the
user (2026-09-20): *"hãy cho lô trình để có thể giao dịch thật"*.
**Risk:** 🟡 — a report; the risk is scaling capital on a stage that only looked like the
backtest.
**Complexity:** M — one script that joins the journal to the candidate's backtest over the same
dates, one report per stage, repeated.
**Epic:** [`EPIC-026`](../README.md)
**Depends on:** [`EPIC-026Q`](EPIC-026Q_mainnet_caps_and_typed_acknowledgement.md),
[`EPIC-026R`](EPIC-026R_mainnet_read_only_first_contact.md); `O3` (stage sizes)

---

## 1. Context and problem

A backtest assumes a fill price, a fee and no rejection; a live stage produces real ones. The
difference between them, per trade, is the only number that says whether the candidate's edge
survived contact with the market — and whether the next capital stage is justified. `BOT-078`
made the backtest honest about fees; nothing yet makes the live result comparable to it. The
journal (`EPIC-026G`) holds the live side; the static engine holds the other over the same dates.

## 2. Acceptance criteria

- [ ] `scripts/epic026s_live_vs_backtest.py --since {stage start} --until {stage end}` re-runs the
      candidate's static backtest over the stage's dates on the vault's candles and joins it to the
      journal's fills by signal time: per trade, backtest fill vs live fill, slippage in ticks and
      basis points, fee assumed vs fee charged, trades the backtest took and live did not (blocked,
      rejected, breaker) and the reverse.
- [ ] Summary lines: mean and worst slippage, fee ratio, trade-count agreement, live PnL vs
      backtest PnL over the stage, and the `CandidateVerdict` re-judged on the live numbers.
- [ ] `Tasks/reports/live_stage/{n}_{start}_{end}.md` per stage with the script's output, the
      stage's caps and capital, every breaker or watchdog event, and the user's decision at the
      bottom: **increase to …**, **hold**, or **stop**, quoted verbatim (🟢 User decision).
- [ ] The next stage's caps in `app_config.json` change only after that decision is recorded,
      and the pull request that changes them links the report.

## 3. Design

The join is a pure function in `backtesting/domain/` (it reads `BacktestResult` trades and
journal fills as DTOs; `backtesting` is downstream of `trading`'s contracts through the Published
Language only — the script passes the fills in, the domain does not import the journal). The
script is thin, like `EPIC-026O`'s. No UI: this report is read once per stage, by the person who
decides.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/backtesting/domain/live_vs_backtest_join.py` | Pure join and summary |
| `scripts/epic026s_live_vs_backtest.py` | The script |
| `tests/unit/modules/backtesting/domain/test_live_vs_backtest_join.py` | Matching by time, slippage sign, missing on either side |
| `tests/unit/scripts/test_epic026s_live_vs_backtest.py` | Output against fakes |
| `Tasks/reports/live_stage/{n}_….md` | One per stage |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Join | unit | unit | each class of difference named; slippage sign correct for both sides |
| Script | unit | unit | summary lines present |
| Stage 1 | the report after the first 14 days | human | user decision quoted |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
