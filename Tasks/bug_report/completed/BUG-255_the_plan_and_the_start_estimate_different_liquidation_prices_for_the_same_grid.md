# BUG-255 — The Plan row and the start's plan-risk check estimated different liquidation prices for the same grid (633.35 against 656.49)

- **Reported:** 2026-10-21 (the owner, noticed while the Grid of BUG-254 started; coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`)
- **Severity:** 🟡 P2 — real money: at 7x the start passed `plan risk OK LIQUIDATION_ESTIMATE` with 1.51 between the exit and the estimated liquidation, where the Plan row had promised 24.65; a stop that close to liquidation may be skipped by a gap
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** The Plan and the Start judged one grid on plans made at different entry prices (the liquidation estimate moves about 0.4–0.6 per point of entry price, which does not by itself explain the owner's 633.35 against 656.49: that divergence stays open) and the Start passed no daily ATR, so a stop 0.23% before the estimate only warned in the Plan and passed at Start; fixed by an ATR-free refusal floor judged by the one function both call (`STOP_LOSS_TOO_CLOSE_TO_LIQUIDATION`, 1% of the exit, the owner's choice of 2026-10-21; an ATR-tied floor follows).
- **Context:** Plan a Futures Grid → bots (`src/modules/bots/`) → `domain/grid/` (`futures_grid_checks.py`, `grid_evaluation.py`), `application/services/venue/futures_start_checks.py`
- **Environment:** Desktop app, Futures Mainnet, `master-warrior` 970b77b. Not captured: the plan's quantities and the symbol's brackets at the time.

## Reproduction
Not reproduced: the owner's brackets and the plan's quantities were not captured. Start the same grid (BNBUSDT LONG 698–807, 27 grids, 34 USDT, 7x, stop 658) and compare the `[plan-risk]` line at start with the Plan row.

## Symptom
```
UI Plan:        liquidation near 633.35, 24.65 before the exit at 658
Start (log):    plan risk OK LIQUIDATION_ESTIMATE ... worst case: 656.49, 1.51 before the exit at 658
```
Expected: one estimate for one plan, or a start that says why it moved.

## Root cause
Established at `68e1227` (the first report's facts at `970b77b` stand):
- Both callers run `judge_futures_plan` (`futures_grid_checks.py`) on a `PlanRiskInputs`. The liquidation estimate reads only the plan, the grid's leverage and the brackets (`_estimate`), never the mark or the setting, so the two builders differ in the estimate only through the **plan** each was made at: the Plan row at the screen's last price clamped into the range (`grid_evaluation.py` `_risk_verdicts`), the Start at the price it enters at (`grid_start_sequence.py` `run_at`).
- That the estimate moves with the entry price was measured with the real code (BNBUSDT LONG 698–807, 27 grids, 34 USDT, 7x, stop 658, a bracket table of the test fixture): plans at 700 / 730 / 760 / 790 give a worst-case liquidation of 602.41 / 623.67 / 637.91 / 644.97, i.e. a gap to the exit of 55.59 / 34.33 / 20.09 / 13.03. The review of this fix swept the whole range with the fixture's brackets: the estimate peaks at 645.85 (a plan made at 806), so the entry price **cannot alone** produce the Start's 656.49. Another input differed: the brackets the two reads used, or the plan's quantities. The divergence itself is **not explained and stays open** (see \"Not fixed here\"); the OK verdict now says the plan's price and worst-case position, so the next occurrence tells the inputs apart from one `[plan-risk]` line.
- The Start passes no `daily_atr` (`futures_start_checks.py` `FuturesStartReads.risk_inputs`), and `_stop` skipped `STOP_LOSS_NEAR_LIQUIDATION` without it; that verdict is a WARNING and never refuses a start (`FuturesStartChecks.refusal` keeps `verdict.refuses`). A stop 1.51 before the estimate (0.23% of the exit) could not stop a start in either place.

## Fix
`STOP_LOSS_TOO_CLOSE_TO_LIQUIDATION` (REFUSED) in `futures_grid_checks.py` `_stop`: the exit closer to the estimated liquidation than `FuturesGridThresholds.min_liq_gap_ratio` (1%) of the exit's price. It needs no ATR, so the Plan, which shows it, and the Start, which refuses on it, judge the same band by the same function (`FuturesRiskGuard.judge_plan`). Its words name the price the plan was made at and the minimum gap. The ATR buffer stays an advisory. The field map and liquidation row know the new code. The owner chose 1% on 2026-10-21 and asked for an ATR-tied floor later ([decision](../epics/EPIC-039_futures_venue_profile/DECISION_2026-10-21_a_stop_too_close_to_liquidation_is_refused.md)).

## Regression test
`tests/unit/modules/bots/domain/grid/test_a_stop_too_close_to_liquidation_is_refused.py`: a stop half a floor above the estimate is refused with and without an ATR, twice the floor is not; the floor comes from the thresholds; a negative floor is refused; the boundary is pinned (exactly the floor passes, a cent under is refused, both sides); the OK verdict carries the plan price and position. Red before: the field and the code did not exist.

## Verification
Commit tier, `tests/unit/modules/bots`, `tests/integration/modules/bots` (5855) green locally. Not run on a real exchange.

## Not fixed here
The unexplained divergence of 633.35 against 656.49: open hypotheses are different brackets between the cached Plan read and the Start's fresh `SymbolBrackets.refresh`, and different plan quantities; a follow-up bug is filed when a `[plan-risk]` line with both inputs is captured. The 1% floor was chosen by the owner ([decision](../epics/EPIC-039_futures_venue_profile/DECISION_2026-10-21_a_stop_too_close_to_liquidation_is_refused.md)).
Passing the daily ATR to the Start (it needs the stored daily candles in `FuturesStartReads`' wiring) and showing the Plan's entry price beside its estimate; neither changes a refusal.
