# EPIC-027E — A saved backtest report states which market it simulated

**Status:** 🔵 Backlog
**Source:** follows the user's *"back test theo spot"* request, 2026-09-26.
**Risk:** 🟢 — additive schema change with a default; old reports must still load.
**Complexity:** S — one config field, the ignored/rejected counters, a schema version bump.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027B](EPIC-027B_spot_mode_in_the_backtest_engine.md), [EPIC-027C](EPIC-027C_exchange_filters_on_simulated_fills.md)

---

## 1. Context and problem
- Report schema v1 serializes `long_leverage`/`short_leverage` and each trade's side and leverage
  (`src/modules/backtesting/.../backtest_report_serializer.py:82-83,135-136`). The loader requires
  those fields (`backtest_report_loader.py:202-203,280-281`).
- Nothing records the market, so a Spot report and a Futures report of the same symbol cannot be
  told apart. That undermines the side-by-side comparison (`BOT-115D`).

## 2. Acceptance criteria
- [ ] A new report carries `market_type`, the ignored-short count and the exchange-filter provenance.
- [ ] A v1 report still loads. Its market is shown as "not recorded (pre-EPIC-027)", not guessed.
- [ ] The comparison dialog warns when the two reports simulate different markets.

## 3. Design
- A schema version bump with defaulted fields, following the precedent of `BOT-115A`'s versioning.
  A missing field loads as "not recorded" (`domain-truth-rule.md`: never invent a value).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/backtesting/contracts/backtest_report.py` | fields and version |
| serializer / loader | write and read the fields; v1 compatibility |
| comparison dialog logic | the market-mismatch warning |

## 5. Testing
- Unit: round-trip v2; load a v1 fixture; the mismatch warning.
- Not run yet.

## Notes
- Side finding recorded here so it is not lost: the serializer does not write `break_even_trigger_pct`,
  the trailing fields or `partial_take_profit_levels` (`backtest_report_serializer.py:76-86`). A
  report therefore does not fully reproduce its run. Fix it in the same schema bump if it stays S;
  otherwise file it as its own `BOT` task.
