# EPIC-039G — A Futures bot's costs are real: commission from the account, funding every eight hours, realized profit

**Status:** ✅ Done (2026-10-13)
**Source:** the owner, 2026-10-10 (the earlier numbers on step size versus fees); [DESIGN §3, §6](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🟡 — money figures shown to the owner; a fee counted twice or not at all misstates profit
**Complexity:** M — a cost port, a funding reader, an event field, PnL and progress changes
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (progress and PnL words).
**Design:** [DESIGN §3, §6](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§1, §8](../RESEARCH_2026-10-10_futures_grid.md)
**Branch:** `claude/epic-039g-futures-costs`
**Depends on:** [039A](EPIC-039A_venue_profile_seam.md), [039C](EPIC-039C_futures_fake_exchange_matching.md) (the fake charges funding).

---

## 1. Context and problem
Spot's cost model is maker/taker, with the fee often taken from the base asset (the opening buy's fee shrinks the base the SELL levels may sell). Futures fees are charged in the quote asset, and a held position pays or earns **funding** every 8 hours (Pionex, RESEARCH §1), which appears in the wallet, not in a fill. The owner's step-versus-fee numbers (step % − 2 × fee) change on Futures (typically lower fees, plus funding), and PnL must include both.

### Facts verified on `master-warrior` `076d339`
- `bots/domain/bot_kind_inputs.py` `ExchangeTerms.maker_fee/taker_fee`; `bots/domain/grid/grid_spacing.py`: "the step / buy − 2 × fee"; `grid_checks.check_break_even`, `check_min_step`; `grid_pnl.py` (68 lines), `grid_runtime.py` (`LevelOrder.base_fee`, `quote_fee`, `paired_buy_fee_quote`).
- `trading/adapters/binance/futures_commission_rate_reader.py` (`FuturesCommissionRateReader.commission_rate(symbol)`) and `contracts/i_commission_rate_reader.py`, `commission_rate.py`: the account's rates are already read for Futures.
- `trading/contracts/events/order_filled_event.py`: `fee_amount`/`fee_asset` are `None` for Futures, with the stated reason "`ORDER_TRADE_UPDATE` carries no per-fill commission field at all". **This is understood to be wrong** (Binance's order update is believed to carry commission `n`/`N` and realized profit `rp`) — **to verify on the official page** (RESEARCH §8) and fix the docstring and the parser if so. `trade_id` is `None` for Futures too.
- `trading/contracts/mark_price.py` has the mark price only; `GET /fapi/v1/premiumIndex` is believed to also return the funding rate and next funding time (**to verify**).
- `trading/contracts/futures_order_estimates.py`, `order_estimates.py` already estimate Futures fees/margin for the manual desk — reuse their arithmetic, do not rewrite it.
- `i_order_entry_terms.py` lists "the funding rate and next funding time for the Futures desk header" as a plausible extension.

## 2. Acceptance criteria
- [x] **Docs read first, recorded.** Read 2026-10-13 in Binance's `llms-full.txt` (`https://developers.binance.com/en/docs/llms-full.txt`) and the endpoint pages: `ORDER_TRADE_UPDATE` lists `n`/`N` (commission and asset, "will not push if no commission"), `rp` (realized profit of the trade) and `t` (trade id) — handed over by 039C and re-read; `ACCOUNT_UPDATE` reason `m` includes `FUNDING_FEE`, `bc` is "the balance change except for PnL and commission", and since 2026-08-07 `a.S` names the symbol when `m` is `FUNDING_FEE`; `GET /fapi/v1/premiumIndex` returns `lastFundingRate` ("the Latest funding rate"), `nextFundingTime` and `time` (weight 1 with a symbol); `GET /fapi/v1/income` has `incomeType` `FUNDING_FEE`, `COMMISSION`, `REALIZED_PNL`. Commission is present per fill, so the Futures stream populates `OrderFilledEvent.fee_amount`/`fee_asset` and the docstring is corrected in the same commit (`f7a0169`). The fake's own premiumIndex row already served the funding fields, so no fake change was needed. Evidence: `test_futures_costs_in_the_user_stream.py` (9) and `test_futures_costs_on_the_fake_exchange.py`.
- [x] `ICostModel` (`bots/contracts/i_cost_model.py`): `fees() -> (maker, taker)`, `funding_estimate(position, horizon) -> Decimal | None` (`None` = unknown), `breakeven_step_fraction()`. `SpotCostModel`: maker/taker, funding `Decimal(0)` by definition, break-even `2 × maker`. `FuturesCostModel`: the account's rates (read per symbol by `FuturesCommissionRateReader` through the terms) and the funding rate; `None` when the rate is unknown. Evidence: `test_grid_futures_costs.py`.
- [x] `IFundingReader` and `FundingRate(symbol, rate, next_funding_at, as_of)` in `trading/contracts`; `FuturesFundingReader` reads `premiumIndex`; a Spot venue has no reader and answers `NotApplicable.ON_THIS_VENUE` through `GetFundingRateQuery` and `IOrderEntryTerms.funding_rate_for`. A blank rate is `MarketPriceUnavailableError`, never zero. Evidence: `test_funding_rate_query.py`, the fake-server read in `test_order_entry_reads_against_fake_server.py`, `test_the_funding_rate_is_read_through_the_venue_terms`.
- [x] Plan checks. `check_min_step` / `check_break_even` were already reading `terms.maker_fee`, which for a Futures venue is the account's rate (`exchange_terms_for` ← `FuturesCommissionRateReader`); unchanged thresholds and codes, and a test pins `two_maker_fees` to `FuturesCostModel.breakeven_step_fraction()` and shows the same step passes at 0.02 % and is refused at 0.1 %. New `FUNDING_ADVERSE` (advisory, `grid_funding_check.py`, `FuturesGridThresholds.funding_adverse_share` = 25 %): one funding interval's cost on the plan's opening net position against that share of `cycle_profit_quote`; long pays a positive rate, short a negative one, neutral opens none.
- [x] PnL and progress. `GridRuntime.commissions` and `funding_total` (codec: absent reads as 0), `PnlSummary.commissions` and `.funding` (`BotProgress.pnl` carries them; `BotProgress`'s own Spot fields are untouched). Funding is booked through `FundingChargedEvent` → `BotEventRouter.on_funding` → `IBotFacts.on_funding`; it is in `total`, never in `grid_profit` or `realised`. Commission reaches PnL through the fill's quote fee exactly as a Spot quote fee does. Realized profit per cycle comes from the fills, as Spot's does; the stream's `rp` is carried to the bot (`BotOrderFill.realized_profit`) for the position executor (039H) and is **not** summed here: a second source for the same number is the double counting this task forbids. Evidence: `test_grid_futures_costs_in_the_run.py`.
- [x] No fee is counted twice — **given a trade id**. The emitter claims a trade by `(symbol, trade_id)` and the bot's applied fills do the same, so a duplicate report adds its commission once (tested at both layers). **Until 039D parses `t`, a Futures fill still carries `trade_id = None` and a duplicated Futures report is counted twice** (found by 039C); the end-to-end duplicate test on the fake belongs to 039D and is the check that closes this criterion for Futures.
- [x] Spot PnL and progress are unchanged for the Spot oracle inputs: the earlier figures are the same arithmetic with a zero funding term (`test_spot_pnl_is_unchanged_for_the_oracle_inputs`), and the existing Spot suites (`tests/unit/modules/bots`, `tests/integration/modules/bots`, 2 872 + the new ones) pass unchanged.

## 3. Design
Costs behind one port (`ICostModel`) so the planner's break-even, the readiness text and the PnL read the same numbers (the `EPIC-037` lesson: one place). "Unknown" is a value (`None`), never zero (`domain-truth-rule.md`, the `ExchangeSnapshot` pattern): a funding rate that could not be read says so rather than showing 0.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `trading/adapters/binance/futures_user_data_stream.py`, `futures_order_updates.py`, `order_filled_event.py` | commission and realized profit (after verification) |
| `trading/contracts/funding_rate.py`, `i_funding_reader.py` (new); `adapters/binance/futures_funding_reader.py` (new) | funding read |
| `bots/contracts/i_cost_model.py` (new); `application/services/cost_model_spot.py`, `cost_model_futures.py` (new) | the port and two adapters |
| `bots/domain/grid/grid_checks.py`, `grid_derived.py`, `grid_pnl.py`, `contracts/bot_progress.py` | Futures-aware figures behind the profile |
| `tests/sanity/fake_exchange/` | funding rate endpoint (with 039C) |

## 5. Testing
Tier: unit; integration on the fake (funding).
All six written, plus the check, the router and the codec. Mutation checks run: a `with_funding` that adds nothing and a flipped funding sign turn five of them red.
- `test_futures_fees_come_from_the_account_and_set_the_break_even_step`
- `test_a_position_across_a_funding_time_pays_or_earns_and_progress_shows_it_separately`
- `test_an_unreadable_funding_rate_is_unknown_not_zero`
- `test_funding_adverse_warns_when_it_eats_the_cycle_profit`
- `test_a_fill_fee_reaches_pnl_once_whichever_report_comes_first`
- `test_spot_pnl_is_unchanged_for_the_oracle_inputs`
Run 2026-10-13, green.

## Pitfalls
- A fee in the **base** asset exists on Spot only; the Spot sizing rule "net of the opening fee" must stay behind the Spot adapter.
- Funding is a wallet event (`ACCOUNT_UPDATE` reason), not a fill: counting it in the grid's realized profit would hide a losing grid behind a funding gain.
- Rates differ by account tier; never hard-code 0.02 %/0.05 % (those figures in the owner's chat were from memory).

## Implementation notes (written when done)
**What shipped** (three commits: trading, cost model + check, run accounting).
- **Trading side.** `user_data_event_parser.py` gains `fill_commission`, `fill_realized_profit` and `account_update_funding`; `FuturesOrderUpdates` passes the commission and `rp` to `VenueEventEmitter.order_filled(…, fee, trade_id, realized_profit)` — only those fields, so 039D's `trade_id` change merges beside it. `FuturesUserDataStream` reports funding **before** it needs a position read, because a funding update carries everything in its payload. The funding rate rides on the existing query/handler/`VenueContext` pattern the mark price uses (`funding_reader` is `None` on Spot).
- **A funding update without `a.S`** (before 2026-08-07, or if Binance drops it) is attributed to the one position it lists, else dropped unattributed: funding is never guessed onto a symbol.
- **`FUNDING_INTERVAL` is 8 h**, a constant in `bot_kind_inputs.py`: the pages do not give a per-symbol schedule (039C said so for the fake). `FundingRate.next_funding_at` is the exchange's exact next time; the model's horizon arithmetic is an estimate and labelled one.
- **`venue_assembly.py` is at the 400-line ceiling** (400); the next addition there must split it.

**Decisions taken (recorded, not asked; all reversible):** the cost model sits as a port with two adapters but the domain checks keep reading `ExchangeTerms` fees — the same numbers, pinned equal by a test — rather than pushing a port into the pure domain; `commissions` is kept on the run although it is already inside the realised figures, so the screen can name what trading cost; `rp` is carried, not summed.

**Not done, by design:** nothing renders `commissions`/`funding` yet (the Futures UI is 039J); no Futures executor exists, so `planner_numbers` reads the funding rate only when a profile with funding is a bot venue (`BOT_MARKETS` still excludes Futures until 039H) — covered by `funding_view_of`'s tests, not by a running Futures bot. Funding has no unique id in `ACCOUNT_UPDATE`, so a replayed funding update could not be told from a new one; none is replayed on a reconnect today.

## Resume
Done. Hand-offs: **039D** — parse `t` into `trade_id` and add the duplicate-Futures-fill test (the end-to-end half of the "no fee twice" criterion); **039H** — read `BotOrderFill.realized_profit` and `IBotFacts.on_funding`; **039J** — show `PnlSummary.commissions`/`.funding` and the `FUNDING_ADVERSE` advice (`NO_FIELD` lists it as having no single field); **039K** — the funding history (`GET /fapi/v1/fundingRate`) behind `IFundingReader`.
