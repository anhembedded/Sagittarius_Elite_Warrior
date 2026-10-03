# EPIC-029C — The Grid planner turns the user's parameters into a plan, derived values and a verdict per check

**Status:** 🔵 Backlog
**Source:** [`PRO-006`](../../../proposal/PRO-006.md) §1.5 and §4.2, from the user's report
`grid_trading_phan_tich.docx`. The user's rule, 2026-10-03: *"các param có thể thay đổi mà, còn bot
grid tính toán dựa trên param và output xem các param có hợp lý ko, chứ ko cố định param vào số
nào"* ("the parameters can change; the Grid bot calculates from them and outputs whether they are
reasonable; it does not fix them to any number").
**Risk:** 🟢 — pure domain code with no orders and no I/O. A wrong formula is caught by
known-answer tests.
**Complexity:** M — two spacing models, about ten derived values, about eight checks and two new
indicators.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029B` for `Verdict` and `IBotKind`.

---

## 1. Context and problem

The report gives the formulas and the advisory thresholds (PRO-006 §1.5). Nothing in the tree
computes them, and there is no ATR or Bollinger Bands indicator
(`src/support/indicators/indicators/` has EMA, MACD, RSI, SupportResistance and WMA only).

## 2. Acceptance criteria

- [ ] **Inputs.** `GridParams` holds:
  - `lower`, `upper` and `grid_count`;
  - `spacing` (ARITHMETIC or GEOMETRIC) and `capital_quote`;
  - `stop_loss` and `take_profit`, each a price, a percentage, or off;
  - `maker_fee` and `taker_fee`.

  Every field is user input with no hidden constant.
- [ ] **Levels.** `plan(params, terms, last_price)` returns a `GridPlan` whose levels are rounded to
  `tick_size`, BUY down and SELL up, the same rule as `order_quantity_rounding_policy.py:69-83`.
  - Quantities are rounded to `step_size`.
  - Levels strictly below `last_price` start as BUY and levels strictly above it as SELL.
  - The level nearest the price (within half a step) stays EMPTY, so no order is marketable at the
    taker fee (ADR §3.2).
  - The opening base purchase is the total quantity of the SELL levels.
- [ ] **Known answers.** Against the report's example (60,000–70,000, 10 grids, 0.1% fee, 10,000
  USDT at 65,000):

  | Value | Expected |
  | :--- | :--- |
  | Arithmetic step | 1,000 |
  | Net profit per grid | 1.467% at the bottom, 1.249% at the top |
  | Geometric ratio | ≈1.01553 |
  | Value at the lower limit | 9,457 |
  | Buy-and-hold at the lower limit | 9,231 |
  | Cycles to recover | ≈40 |
- [ ] **Three refusals, each a certain loss or a certain rejection,** and no others (🟢 decision 5,
  PRO-006 §4.2; ADR D14, D21):
  - `step% ≤ 2 × maker`. Both ladder legs pay the maker fee, so every cycle loses money; this is
    the report's `2×fee` with the fee model of ADR D14;
  - a capital per level below the venue's `min_notional`, which the exchange rejects;
  - a capital per level above `max_notional_per_order`, which trading rejects (ADR D21, O5). The
    verdict names the cap and the largest capital that would pass.
- [ ] **Warnings,** each carrying its threshold as an editable default and the measured value:
  - a step below 0.5%;
  - a range outside 2–4× ATR(14) on the daily timeframe, when candles are available;
  - a stop loss or take profit outside 3–8% of the range edge;
  - ARITHMETIC on a range wider than 20%;
  - a stop loss at or above the lower limit;
  - a take profit at or below the upper limit.
- [ ] **Verdicts.** Every verdict has a severity (OK, WARNING or REFUSED), a stable code, a
  human-readable reason and the numbers behind it.
- [ ] **Suggestions,** offered values only:
  - `atr_range(candles, period=14, multiple=k)`;
  - `bollinger(candles, period=20, deviations=2)`.

  Both are pure functions in `src/support/indicators/` with known-answer tests against a published
  worked example.
- [ ] **Coverage.** Every formula and threshold is covered by a test that fails when the formula
  changes; this is checked by mutation (`testing-rule.md`).

## 3. Design

- **Pure functions over frozen dataclasses** in `bots/domain/grid/`:
  - `grid_params.py`, `grid_plan.py` and `grid_spacing.py` (the two models behind one function);
  - `grid_checks.py` (one function per check, returning a `Verdict`);
  - `grid_derived.py` (profit per level, value at the edges, cycles to recover).
- **No floats for money.** `Decimal` throughout, matching `OrderRequest`.
- **No indicator inheritance.** ATR and Bollinger take a sequence of candles (high, low, close)
  and are not `IIndicator`s (ADR D17). They live in `src/support/indicators/bands.py` and
  `volatility.py`.
- **Exchange data comes in as a value.** `terms` is a value object carrying `tick_size`,
  `step_size`, `min_notional` and fees. The F2b executor and the F2a backtest each fill it from
  their own source: `order_entry_terms` live, and recorded terms in the backtest.
- **`GridKind` implements `IBotKind.validate`** by delegating here.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/*.py` (new) | the planner |
| `src/modules/bots/domain/grid/grid_kind.py` (new) | `IBotKind.validate`, `overlay` (data only) |
| `src/support/indicators/volatility.py`, `bands.py` (new) | ATR, Bollinger Bands |
| `tests/unit/modules/bots/domain/grid/**`, `tests/unit/support/indicators/**` | known-answer, boundary and mutation tests |

## 5. Testing

Unit tests only:

- the report's example as known answers (table above);
- the boundaries of every check, at exactly the threshold and one tick either side;
- the two refusals;
- the rounding direction;
- a mutation run over `grid_checks.py` and `grid_spacing.py`, with the surviving mutants recorded.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
