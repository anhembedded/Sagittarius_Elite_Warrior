# BUG-211 — A Spot Grid the Plan called ready bought ~34.7 USDT at market, then halted with no ladder: its first SELL was under the 5 USDT minimum

- **Reported:** 2026-10-15 (the owner, Spot MAINNET, bot `ke95g7` "Test_real_cash", real money)
- **Severity:** 🔴 P1. Real money was spent at market on a start the Plan showed as ready, and the bot halted with nothing resting. The loss is the spread and fee of an unwanted round trip, and an exposure the user did not choose.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** The Plan passed a 35 USDT ETHUSDT Grid whose first SELL the executor sized to 0.0020 ETH (4.79 USDT), so the opening market buy went out and the start halted on `min_notional`. Cause: `check_min_notional` judged each level's notional less the fee, the executor floors the quantity to the step after the fee, so the two sized a SELL differently. Fix: one sizing function, `grid_order_sizing`, serves the check and the executor, and the executor judges the ladder before it buys.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), starting a Spot Grid → `bots` → `domain/grid/` (pre-start check, sizing) and `application/` (`GridStartSequence`, `SpotOpening`)
- **Environment:** Spot MAINNET, ETHUSDT (step 0.0001, tick 0.01, minimum notional 5, taker fee 0.1%), Lower 2348, Upper 2667, 7 grids, arithmetic, capital 35 USDT, SL 2259, TP 2805, price about 2363.77. Never tested on a live exchange by the fix: tests use the simulated venue.

## Reproduction
1. Plan a Spot Grid with the Environment's numbers. Price 2363.77 is above the lowest level, so seven levels are SELLs and level 0 stays empty.
2. Read the Plan: no refusal, no warning, Start enabled.
3. Start.

Expected: the Plan refuses, naming the order. Nothing is bought.
Actual: a market buy of 34.74 USDT, then `L1 SELL 0.002 @ 2393.58 -> min_notional` and `STARTING -> HALTED`.

Frequency: deterministic for these inputs (reproduced in `grid_order_sizing` tests and on the real `GridExecutor` against the simulated venue).

## Symptom
```text
17:28:55,414 GridExecutor WARNING Bot ke95g7: 0.00008380 ETH from earlier runs stays on the account and is not traded by this run (cost 0.2045...) [earlier-runs]
17:28:56,210 GridExecutor INFO Bot ke95g7: opening buy slice 1 of 34.74028950 USDT -> done SEW-ke95g7-bd3e091168
17:28:56,476 OwnerInventory INFO Derived inventory for ke95g7 on ETHUSDT: 0.01458540 ETH at cost 34.50403400 (from a checkpoint, 1 order(s)).
17:28:56,616 GridExecutor INFO Bot ke95g7: opening buy counted from the exchange's record: 0.01458540 ETH held, the ladder sells 0.01400000
17:28:57,038 GridExecutor INFO Bot ke95g7: L1 SELL 0.00200000 @ 2393.58000000 -> min_notional
17:28:57,048 GridExecutor WARNING Bot ke95g7: STARTING -> HALTED on start_refused (start_refused: L1 SELL: min_notional) [bot-transition]
```
Also reported the same day: the price-band refusal said "would buy about 34.10 of the base asset", for a quote amount.

## Root cause
Two sizings of one order. `check_min_notional` (`src/modules/bots/domain/grid/grid_checks.py`, before the fix) took the smallest `plan.order_levels` notional and multiplied it by `1 − taker_fee`: 0.0021 × 2393.58 = 5.03, × 0.999 = 5.02, so it passed. The executor lays `sells_net_of_opening_fee(plan, …)` (`opening_spot.py`, `grid_ladder.py`): each SELL quantity × (1 − fee) **floored to the step**: 0.0021 → 0.002099 → 0.0020, worth 4.79, which Binance refuses. The fee was modelled; the step floor was not. A second defect made the first costly: `GridStartSequence.run` sent the opening market buy (`SpotOpening._buy_opening`) before it knew the ladder it feeds could be placed, so the refusal came after the money was spent.

The same class survives in the counters: a counter SELL after a BUY fills is the level's bought quantity net of the fee and floored (here 0.0019 ETH, 4.63 USDT), and the counter BUY after a SELL fills is the level's `buy_quantity`; neither was ever judged before Start.

The price-band message called its quote figure `of the base asset` (`grid_range_checks.py`).

## Fix
- `src/modules/bots/domain/grid/grid_order_sizing.py` (new): the one sizing. `opening_ladder` (the executor's ladder), `sized_orders` (those orders plus the first counter of each pair of levels), `find_breach` (the smallest start order, else the smallest counter, under the minimum, with the capital that clears it, found by searching the real sizing rather than by proportion).
- `grid_checks.check_min_notional` judges `find_breach`; its refusal names the order, its worth, the minimum and the capital.
- `SpotOpening.open` lays `opening_ladder`; `GridStartSequence.run` calls `find_breach` before the opening, and a breach is a WARNING `[order-below-minimum]` and a `start_refused` with nothing spent. An INFO `[ladder-sizing]` line states the smallest order's quantity, price and notional.
- `grid_ladder.net_of_buy_fee` is the one rule for a SELL's quantity, used by `sells_net_of_opening_fee` and the counters.
- The price-band message says what is spent in the quote asset and what is bought in the base.

Searched and left as is: `grid_replay.py` (backtest) already lays `sells_net_of_opening_fee`, the same function the executor's ladder is built on; restart reconcile and a resume size from the inventory held and leave a level EMPTY under the minimum (`resized_for_inventory`, `buys_within_capital`); a counter sized from a partial fill is dropped under the minimum (`_settle_short`); the Futures opening lays the plan unchanged (its fee is paid in quote) and `opening_ladder` returns it unchanged.

## Regression test
- `tests/unit/modules/bots/application/services/test_grid_start_refuses_before_spending.py::test_the_owners_start_is_refused_before_any_order_is_sent`: real `GridExecutor` on the simulated venue with the owner's numbers; failed before the fix because the book held the opening market buy, passes with an empty book. Its parametrised sibling is the property: over capitals × grid counts, a start either sends nothing or sends only orders at or above the minimum.
- `tests/unit/modules/bots/domain/grid/test_grid_order_sizing.py`: the owner's plan is refused with `L1 SELL`, 4.79 and the minimum; the capital the refusal names passes; the refused order is one the executor lays; check-passes ⇒ every order meets min notional and step over capitals × grids × prices; a quantity rounding to nothing is a breach, not a skipped order. The first tier failed before the fix because the check returned no verdict at all for these inputs.
- `test_grid_range_checks.py::test_the_below_range_refusal_states_a_quote_amount_and_a_base_quantity`.
- `test_grid_checks.py` boundary test rewritten to the order as sent (the old one fixed the fee-only formula this bug removes).

## Verification
Commit tier: `ruff check` and `ruff format --check` over `src tests tools scripts` clean; `check_skill_prompt_references.py` OK; `pytest tests/unit/modules/bots tests/unit/architecture` green. `mypy` reports 226 errors in 47 files of the unmodified tree (environment, none in a changed file). The `-Full` run is GitHub's. Positive proof the new mechanism ran: the executor test's refused start leaves `world.book.requests == []` with the `start_refused` detail naming `L1 SELL`.

Not verified: no order was placed or simulated on Binance. `minQty` is not part of `ExchangeTerms`, so it is not judged (the minimum notional binds first at ETH prices); the opening buy's actual fill can still differ from the planned quantity, which `_count_opening` already refuses afterwards.
