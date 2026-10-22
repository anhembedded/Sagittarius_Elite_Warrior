# BOT-235 — The Plan says what the stop loss costs and what the take profit earns

**Status:** 🟡 In progress
**Board:** The Plan showed only the exit prices; it now carries two estimated rows from the domain (`grid_exit_estimate.py`): the loss if the price runs straight to the stop loss (the whole ladder filled, marked to the stop) and the gain if it runs straight to the take profit (the sells that fill, the rest closed there), both net of fees, in the quote asset and as a share of capital, with the path assumed and funding left out; a saved bot at rest also shows the plan guard's liquidation estimate instead of "not in the bot's record".
**Source:** the owner, 2026-10-22, with a screenshot of the Bots screen's Plan section, via the coordinator (session_016sGQHsRy729Fp4cY1cTXfu): "I need more information here: if the stop loss hits, how much do I lose; if the bot runs straight up to TP, how much do I make" (translated).
**Risk:** 🟢 — a read-only estimate over an existing plan; no order, setting or stored field changes
**Complexity:** M — one pure domain function, one words file, one facts field pair, two rows
**Epic (optional):** None
**SPEC (optional):** [SPEC-014](../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None

---

## 1. Context and problem
The owner's Plan (Futures Testnet BNBUSDT, capital 200, 730–750, stop 721, take profit 757) lists the exit prices but not what they mean in money, and the Liquidation price row read "not in the bot's record (the exchange reports it while it runs)" for a bot that had not run, although the plan guard already estimates it (`bot_detail.py` → `detail_for` showed the estimate only for an unsaved design, `BUG-261`). Checked for an existing worst-case loss: `grid_derived.py` → `EdgeValues` is the value at the *range edge*, before fees, for `cycles_to_recover`; `futures_worst_case.py` gives the largest position, not a loss; `futures_liquidation.py` → `loss_of_liquidation` is the liquidation case. None is the loss at a stop with fees, so nothing is unified: the new function reuses their position book.

## 2. Acceptance criteria
- [x] *Loss at stop loss (estimate)*: the price runs straight from the plan's last price to the stop (down for Long and Neutral, up for Short), every resting order on the way fills, the whole position is closed at the stop; maker fee on the fills, taker fee on the opening trade and the close; funding and slippage left out.
- [x] *Gain at take profit (estimate)*: the price runs straight to the take profit, every order that fills on the way counts, whatever is left is closed there, net of fees; Short mirrors; for Neutral the short leg closes at the take profit, so the figure is a loss and is shown with its sign.
- [x] Each row shows the amount (signed, toned), its share of the capital, the path assumed and what is left out, and is labelled "(estimate)"; an exit that is off, a bot with a run, or parameters that make no plan hide the row.
- [x] The numbers are the domain's, built on the position book the Futures replay uses and its fee rule, never a UI-side formula.
- [x] A bot at rest shows the plan guard's liquidation estimate (the one `BUG-255`/`BOT-227` judge the stop against); "the exchange reports it while it runs" stays only where no estimate exists.
- [x] Unit tests with hand-worked figures: the owner's numbers (Long), a Short, a Neutral.

## 3. Design
`grid_exit_estimate.py` (domain): `exit_estimates_for(BotKindInputs)` → `estimate_exits(params, plan, terms)` → one `ExitEstimate` per exit. A straight run never reaches a counter order (it rests behind the price), so the fills are the plan's own levels, BUYs from the highest down on a fall and SELLs from the lowest up on a rise, and the result needs no sizing assumption: Spot and position ladders are read alike. The fills go through `PositionBook`; the fees follow `FuturesReplay` (`_open`, `_fill`, `_exit`). The plan comes from `grid_evaluation.py` → `entry_plan`, extracted from `evaluate_grid` so the checks and the estimate size and price it in one place. Words: `ui/bots_screen/exit_estimate_words.py`. The owner's last price is not in the screenshot; the tests use 740, the middle of the range.

Not built (seam only): a path through a candle series is the replay's job; a trailing stop would be one more `ExitEstimate` on `ExitEstimates`.

## 3a. Reuse
`PositionBook` (the Futures replay's book), `ExchangeTerms` fees, `evaluate_grid`'s plan (now `entry_plan`), `liquidation_lines` (the guard's estimate), `write_value`/`signed_key`/`sign_tone`/`signed_percent_of` (formatting and tone), `set_rows_shown` (hiding): used. Capability catalog: no row for an estimate of this kind; nothing to reuse that was not.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_exit_estimate.py` | new: the two estimates |
| `src/modules/bots/domain/grid/grid_evaluation.py` | `entry_plan` extracted, used by `evaluate_grid` |
| `src/modules/bots/ui/bots_screen/exit_estimate_words.py` | new: the rows' text and tone |
| `src/modules/bots/ui/bots_screen/bot_detail.py`, `bot_facts.py` | the facts carry the two texts; the liquidation estimate also for a bot at rest |
| `src/modules/bots/ui/bots_screen/plan_property_rows.py`, `bot_plan_panel.py` | the two rows; hidden while empty |
| `Docs/MODULES/bots/05-building-blocks.md` | the Plan rows drawn |

## 5. Testing
Unit, domain: `tests/unit/modules/bots/domain/grid/test_grid_exit_estimate.py` (owner's Long, Short, Neutral by hand; exit off; no plan; equality with `model_position_along`). Unit, screen: `tests/unit/modules/bots/ui/bots_screen/test_the_plan_says_what_the_stop_and_the_take_profit_are_worth.py` (real `detail_for`). Mutation: the close's taker fee swapped for maker, the ladder's maker for taker: both turn the tests red. Commit tier, `tests/unit/architecture` and the bots unit suite run.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (the Plan panel's rows).

## Implementation notes (written when done)
The owner's figures at last price 740, 2x, maker 0.02%, taker 0.04%: loss at the stop −8.2549 (−4.13% of 200), gain at the take profit +1.3887 (+0.69%). A Long grid's sells have closed the opening position before the price reaches the take profit, so the take profit adds nothing beyond the five sells.
