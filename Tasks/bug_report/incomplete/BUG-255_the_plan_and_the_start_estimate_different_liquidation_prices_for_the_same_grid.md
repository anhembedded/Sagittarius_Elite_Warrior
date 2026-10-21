# BUG-255 — The Plan row and the start's plan-risk check estimated different liquidation prices for the same grid (633.35 against 656.49)

- **Reported:** 2026-10-21 (the owner, noticed while the Grid of BUG-254 started; coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`)
- **Severity:** 🟡 P2 — real money: at 7x the start passed `plan risk OK LIQUIDATION_ESTIMATE` with 1.51 between the exit and the estimated liquidation, where the Plan row had promised 24.65; a stop that close to liquidation may be skipped by a gap
- **Status:** Open
- **Board:** The Plan row said "liquidation near 633.35, 24.65 before the exit at 658" and the start logged "worst case: 656.49, 1.51 before the exit at 658": the two judgements are built from different inputs (`grid_evaluation._risk_verdicts` against `FuturesStartReads.risk_inputs`), and the start passes no daily ATR, so the near-liquidation warning cannot fire; the cause of the 23-point difference itself is Not yet established.
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
Not yet established. Facts, read at `master-warrior` 970b77b:
- Both run the same function, `judge_futures_plan`, but on differently built `PlanRiskInputs`. The Plan row: `grid_evaluation.py` `_risk_verdicts` — `intended_setting(...)`, `plan.last_price` as the mark, `inputs.market.daily_atr`. The start: `futures_start_checks.py` `FuturesStartReads.risk_inputs` — the account's setting read after the gate, the live mark, and **no `daily_atr`** (the field defaults to `None`).
- The liquidation estimate itself (`futures_grid_checks.py` `_estimate`) reads only the plan's worst-case position, the grid's leverage and the brackets, not the mark or the setting. So the 23-point gap must come from a different *plan* (quantities, opening quantity, entry) or different brackets between the two reads, which this report cannot tell apart.
- With `daily_atr=None`, `_stop` skips `STOP_LOSS_NEAR_LIQUIDATION` (`futures_grid_checks.py`, the `atr is not None` test), so a 1.51 gap cannot even warn at start; and that verdict is a WARNING, which never refuses a start (`FuturesStartChecks.refusal` keeps only `verdict.refuses`).

## Fix
Pending. One builder of `PlanRiskInputs` for both callers would remove the first difference by construction; whether the start should refuse a stop closer to liquidation than a floor is the owner's decision (it is a product rule, not a repair).

## Regression test
Pending: a test that builds the plan and the start's inputs for one grid and requires the same liquidation price, and the same verdict set.

## Verification
Not run.

## Suggested next steps
1. Capture the Plan row and the `[plan-risk]` line from one start, with the plan's quantities, to see which input moved. 2. Share one `PlanRiskInputs` builder between `grid_evaluation` and `FuturesStartReads`. 3. Owner decision: should a start refuse an exit within a floor of the estimated liquidation?
