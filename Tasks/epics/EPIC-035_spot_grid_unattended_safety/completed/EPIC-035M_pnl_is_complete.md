# EPIC-035M — PnL is complete: total, BNB fees, HODL benchmark

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L2 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟢 — display and accounting only; no order path
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None
**Board:** the screen leads with Total PnL (every sell against the average cost, net of fees, plus the unrealised at the bot's own saved price), grid profit is one part, a BNB-paid fee is converted at the fill, and the HODL benchmark sits beside it.

---

## 1. Context and problem
Audit L2: BNB-paid fees are ignored so profit is overstated; sells of the opening inventory and exit slices book no realised PnL; unrealised PnL comes from the chart price. This is the field complaint that grid profit and total PnL disagree. Cited: `src/modules/bots/domain/grid/grid_reactions.py:287-317`, `src/modules/bots/ui/bots_screen/bot_facts.py:99-106`. Verify.

**Claims re-verified on `1bad483` (`master-warrior`, 2026-10-08): all four hold; the cited lines moved.**
- BNB fees: `GridFacts._level_fill` split a fee into `base_fee` / `quote_fee` and dropped any other asset (`LevelFill`'s own docstring: "A fee in a third asset (BNB) is not counted here"). Holds.
- Opening-inventory sells and exit slices: `_book_inventory` (`grid_reactions.py:287`) moved inventory and cost but booked no PnL; only `_book_cycle` (sells paired with a buy) added to `realised_profit`. Holds; locked red by `test_selling_the_opening_base_books_realised_pnl_against_the_average_cost`.
- Unrealised from the chart price: holds, and worse than the audit says: `SelectedBot.last_price` was the **planner's design-time price** until a chart candle arrived, so a bot whose chart was closed or not live showed an unrealised figure on a stale price.
- Total PnL was never shown; grid profit was the only earnings figure.

## 2. Acceptance criteria
- [x] Total PnL (realised + unrealised) is the first earnings figure; grid profit reads "of which grid profit" and the unrealised "of which unrealised"; the Bots list's column is Total PnL. Evidence: `test_the_total_is_the_first_figure_with_grid_profit_as_one_part_of_it`, `test_total_pnl_is_realised_plus_unrealised_on_the_bots_own_price`.
- [x] Fees paid in BNB (any third asset) are converted to the quote asset at the fill, from the venue's own `<asset>USDT` book, and included in the cost basis and in a cycle's profit. A fee that cannot be priced is counted (`unpriced_fees`), logged `[unpriced-fee]` and the total says "(N fees could not be priced)". Evidence: `test_bnb_fees_reduce_the_profit` (red when the conversion is dropped), `test_a_fee_in_an_asset_that_cannot_be_priced_is_counted_not_guessed`, `test_fees_that_could_not_be_priced_make_the_total_say_it_is_short`.
- [x] Opening-inventory sells and exit slices book realised PnL (`GridRuntime.realised_total`, against the average cost, net of fees). Evidence: `test_selling_the_opening_base_books_realised_pnl_against_the_average_cost`, `test_an_exit_slice_books_realised_pnl_too`.
- [x] Unrealised PnL uses the bot's own price: the last tick the bot heard, saved with its state at most every 30 s of its own clock (`GridPriceReaction`, `MARK_PRICE_SAVE_SECONDS`), read by the facts; the chart no longer feeds the figures (`take_price`, `show_price` removed). Evidence: `test_the_bots_own_price_is_saved_and_only_every_so_often`, `test_unrealised_pnl_is_what_the_held_base_gained_at_the_bots_own_price`. A bot whose runtime predates the field says "no price yet" until its first tick.
- [x] A HODL benchmark (what the same capital would have gained held from the price the run began at, `start_price`, set by the plan) is shown beside the total. Evidence: `test_the_hodl_benchmark_is_the_capital_held_from_the_start_price`, `test_the_hodl_benchmark_is_shown_beside_the_total`. Fees of the HODL buy are ignored (a benchmark, not a book).

## 3. Design
Domain arithmetic stays `Decimal`; no float enters. One new pure function, `pnl_summary` (`domain/grid/grid_pnl.py`), over the saved runtime; `bot_progress` computes it once and `BotProgress.pnl` carries it, so the list, the figures and any later heartbeat (`EPIC-036`) read the same numbers. The total is the realised of every sell against the **average cost** plus the unrealised of what is held, which is the account's own gain; "grid profit" keeps its paired-cycle meaning and is now labelled as a part. The two are different accountings, so "of which" is the label's claim of containment, not a sum: the realised total and the grid profit differ by what the average-cost basis does to a cycle's paired buy price.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/{grid_runtime,grid_reactions,grid_ladder}.py`, `grid_pnl.py` (new) | the fields, the booking, the summary |
| `src/modules/bots/application/services/{grid_runtime_codec,bot_progress_reader,grid_start_sequence}.py`, `contracts/bot_progress.py` | persistence (old files read), progress, a resume keeps the earnings |
| `src/modules/bots/application/services/{grid_facts,grid_run_context,grid_executor_factory,grid_price_reaction}.py` | the fee conversion and the saved mark price |
| `src/modules/bots/ui/bots_screen/{bot_facts,bot_plan_panel,bots_table_models,bot_detail,selected_bot,detail_effects,bots_presenter}.py` | the figures; the chart price plumbing removed |

## 5. Testing
Unit tier, the real executor on the simulated venue. New: `test_grid_pnl.py` (domain, nine), `test_grid_earnings_on_the_executor.py` (three), two codec tests (round trip; a file written before the fields), six facts tests. Red before: the domain and facts tests failed on the missing fields and signature; the BNB test was also run red by mutation (the conversion dropped: `Decimal('0') == Decimal('6')`). Not run: a real BNB-fee account (never on a real exchange here).

## Implementation notes
- The mark price is saved with the bot's state, so each save is one more write every 30 s per running bot and publishes a `BotChangedEvent`, which is also what refreshes the figures; a bot with no tick for a while shows the last saved price, not "live".
- Not built: a per-fee price history (the BNB price is the book at the moment the fill is processed on the bot's worker, normally within moments of the fill); a fee of a third asset on a bot whose symbol is not USDT-quoted (Phase 1 is USDT only, `ADR D9`).

## Resume
Done. Nothing owed.
