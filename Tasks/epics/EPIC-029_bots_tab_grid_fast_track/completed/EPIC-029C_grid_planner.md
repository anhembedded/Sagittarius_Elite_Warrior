# EPIC-029C — The Grid planner turns the user's parameters into a plan, derived values and a verdict per check

**Status:** ✅ Done (2026-10-03)
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

- [x] **Inputs.** `GridParams` holds:
  - `lower`, `upper` and `grid_count`;
  - `spacing` (ARITHMETIC or GEOMETRIC) and `capital_quote`;
  - `stop_loss` and `take_profit`, each a price, a percentage, or off;
  - `maker_fee` and `taker_fee`.

  Every field is user input with no hidden constant.
- [x] **Levels.** `plan(params, terms, last_price)` returns a `GridPlan` whose levels are rounded to
  `tick_size`, BUY down and SELL up, the same rule as `order_quantity_rounding_policy.py:69-83`.
  - Quantities are rounded to `step_size`.
  - Levels strictly below `last_price` start as BUY and levels strictly above it as SELL.
  - The level nearest the price (within half a step) stays EMPTY, so no order is marketable at the
    taker fee (ADR §3.2).
  - The opening base purchase is the total quantity of the SELL levels.
- [x] **Known answers.** Against the report's example (60,000–70,000, 10 grids, 0.1% fee, 10,000
  USDT at 65,000):

  | Value | Expected |
  | :--- | :--- |
  | Arithmetic step | 1,000 |
  | Net profit per grid | 1.467% at the bottom, 1.249% at the top |
  | Geometric ratio | ≈1.01553 |
  | Value at the lower limit | 9,457 |
  | Buy-and-hold at the lower limit | 9,231 |
  | Cycles to recover | ≈40 |
- [x] **Three refusals, each a certain loss or a certain rejection,** and no others (🟢 decision 5,
  PRO-006 §4.2; ADR D14, D21):
  - `step% ≤ 2 × maker`. Both ladder legs pay the maker fee, so every cycle loses money; this is
    the report's `2×fee` with the fee model of ADR D14;
  - a capital per level below the venue's `min_notional`, which the exchange rejects;
  - a capital per level above `max_notional_per_order`, which trading rejects (ADR D21, O5). The
    verdict names the cap and the largest capital that would pass.
- [x] **Warnings,** each carrying its threshold as an editable default and the measured value:
  - a step below 0.5%;
  - a range outside 2–4× ATR(14) on the daily timeframe, when candles are available;
  - a stop loss or take profit outside 3–8% of the range edge;
  - ARITHMETIC on a range wider than 20%;
  - a stop loss at or above the lower limit;
  - a take profit at or below the upper limit.
- [x] **Verdicts.** Every verdict has a severity (OK, WARNING or REFUSED), a stable code, a
  human-readable reason and the numbers behind it.
- [x] **Suggestions,** offered values only:
  - `atr_range(candles, period=14, multiple=k)`;
  - `bollinger(candles, period=20, deviations=2)`.

  Both are pure functions in `src/support/indicators/` with known-answer tests against a published
  worked example.
- [x] **Coverage.** Every formula and threshold is covered by a test that fails when the formula
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

**Evidence, per criterion:**

| Criterion | Evidence |
| :--- | :--- |
| Inputs | `test_grid_params.py`: every key required and named when missing, a lossless round trip, invalid values refused |
| Levels | `test_grid_plan.py`: sides, the EMPTY level (ties, both edges, half the edge grid beyond an edge, the geometric grid the price sits in), BUY rounds down and SELL up to the tick, quantities rounded down to the step, opening purchase = Σ SELL |
| Known answers | `test_grid_known_answers.py`: step 1,000; 1.467% / 1.249%; ratio 1.01553; 9,457 / 9,231; ≈40 cycles; and the upper edge, +2.3% (10,231) against +7.7% (10,769) |
| Three refusals | `test_grid_checks.py`: each at its threshold and one tick or cent either side; `test_the_three_refusals_are_the_only_refusals` |
| Warnings | `test_grid_checks.py`: every warning at and around its boundary, with its threshold and measured value |
| Verdicts | `domain/verdict.py` (`EPIC-029B`); every check returns severity, code, reason and numbers |
| Suggestions | `test_volatility.py`, `test_bands.py` |
| Coverage | a manual mutation run (below) |

**The mutation run.** No mutation tool is installed, and adding one is a dependency change that needs the user's approval. So a script swapped one operator or constant at a time across `grid_checks.py`, `grid_spacing.py`, `grid_derived.py`, `grid_plan.py`, `volatility.py` and `bands.py`: comparisons, `+ − × ÷`, `2 ×`, the square, the half step, the rounding direction, `min`/`max`. It ran the planner and indicator tests after each swap.

- **First run:** 110 mutants, 21 survived. Ten were inside docstrings. The other eleven were real: equality at `2 × maker`, a zero ATR, the cash that rounding leaves, the half-step neighbour, the half step itself, a doji candle, a zero multiple, zero deviations. Each now has a test.
- **Second run:** 114 mutants, 13 survived. Nine are docstrings. Four are equivalent:
  - `loss <= 0` → `<` in `_cycles_to_recover`: a loss of exactly 0 gives 0 either way, unless a cycle also earns nothing;
  - `last_price < raw[nearest]` → `<=`: at distance 0 the level is EMPTY whichever neighbour measures the step;
  - `nearest - 1` → `nearest + 1` for the half-step neighbour: inside the range the nearest level is always within half its own grid, and below the range both pick level 1;
  - `price < last_price` → `<=` in `_side`: a level equal to the price is always the EMPTY one.

**Review round 1 (PR #318), fixed:**

- **The suggested "largest capital that passes" was itself refused.** A SELL level's base is bought at the last price, so it sells for `capital × price / last_price`, more than its capital. `largest_capital_within_cap()` now divides by the highest SELL markup and floors to a cent. A test feeds the suggestion back (OK) and adds a dollar (refused) at three caps, and pins 10,000 × 65/70 = 9,285.71 for the report at a 1,000 cap. The old test had asserted the wrong formula.
- **A fourth refusal, `TOO_MANY_LEVELS`, a certain rejection.** `ExchangeTerms.max_open_orders` is the venue's `MAX_NUM_ORDERS` and trading's per-owner cap (O1), whichever is lower, filled by the executor. More grids than that is refused before any ladder is built, so `grid_count=200000` costs nothing (it took 3 s). `check_open_orders` then counts the plan's exact orders, because a price outside the range leaves no level EMPTY (`grid_count + 1`).
- **`validate` never raises, now in fact.** `grid_count='²'` passed `isdigit()` and then `int()` raised; the check is `isascii() and isdigit()`. A number too large to compute with (`upper='1e999999999'`) is caught as `ArithmeticError` and becomes `PARAMETERS_UNREADABLE`.

**Decisions made while building, and why:**

- **The fees live in `ExchangeTerms`, not `GridParams`.** The task lists `maker_fee` and `taker_fee` under the inputs. They are a fact of the account (`CommissionRate`), not a choice, so they travel with the venue's filters. The live executor reads them from the account and the backtest records them. No constant fee exists anywhere.
- **`validate(inputs)` takes one `BotKindInputs`** (config, terms, and a `MarketView` with the last price and an optional daily ATR) instead of `validate(config, terms)`. The planner needs the last price, and one parameter object keeps every kind method to one argument.
- **Break-even is judged per grid.** `EVERY_CYCLE_LOSES` refuses when even the widest grid's step is ≤ `2 × maker`. When only some grids are that thin (the upper grids of a wide arithmetic range), it is the warning `SOME_GRIDS_LOSE`, because the others still earn.
- **Unreadable parameters** are one REFUSED `PARAMETERS_UNREADABLE` naming the key, with no plan. This is the absence of a plan, not one of the three judgements, and it lets `validate` never raise.
- **The EMPTY level's "half a step"** is measured in the grid the price sits in, or the edge grid beyond an edge. Inside the range one level is therefore always EMPTY. More than half the edge grid outside the range, none is, and every level holds an order. A geometric test pins the case where the grid below would answer differently.
- **Capital is split over the levels that hold an order**, so the report's 10,000 over 10 orders is 1,000 each. With the price outside the range, all `N + 1` levels share it.
- **The edge values are before fees,** as in the report. They describe where the inventory leaves the user; the backtest counts fees and slippage.
- **ATR and Bollinger live in `support/indicators/indicators/`**, not the package root. The boundary guard admits modules only into the mathematics sub-packages (`_COMPUTATION_SUB_PACKAGES`), so a root-level file would be refused to every module.
- **The indicators' known answers are worked by hand:** a constant true range, gaps up and down, Wilder's recurrence over four candles at period 3, and Bollinger on 1…20 (population variance (n² − 1)/12). No published dataset is in the repository, and an independent closed form is a stronger check than a table copied in.
- **The thresholds are a `GridThresholds` value** the kind is built with: the report's numbers as editable defaults, never read from a constant inside a check.
- **The planner rounds with trading's `OrderQuantityRoundingPolicy`**, not a copy, so `bots` now declares `dependencies = ["trading"]`.

## Resume (optional; while unfinished)
