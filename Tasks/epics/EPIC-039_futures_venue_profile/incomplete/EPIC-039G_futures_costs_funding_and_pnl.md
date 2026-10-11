# EPIC-039G — A Futures bot's costs are real: commission from the account, funding every eight hours, realized profit

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10 (the earlier numbers on step size versus fees); [DESIGN §3, §6](../DESIGN_2026-10-10_futures_venue_profile.md).
**Risk:** 🟡 — money figures shown to the owner; a fee counted twice or not at all misstates profit
**Complexity:** M — a cost port, a funding reader, an event field, PnL and progress changes
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (progress and PnL words).
**Design:** [DESIGN §3, §6](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§1, §8](../RESEARCH_2026-10-10_futures_grid.md)
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
- [ ] The official docs for `ORDER_TRADE_UPDATE` and `ACCOUNT_UPDATE` (commission, realized profit, reason types incl. funding) are read and their page and finding recorded here **before coding**; if commission is present per fill, the Futures stream populates `OrderFilledEvent.fee_amount`/`fee_asset` and the docstring is corrected in the same commit; if it is not, the task records how fees are obtained instead (the trade list) and why.
- [ ] `ICostModel` (`bots/contracts`): `fees() -> (maker, taker)`, `funding_estimate(position, horizon) -> Decimal | None` (`None` = unknown, never zero), `breakeven_step_fraction()`. Spot adapter: maker/taker, `funding_estimate → Decimal(0)` **by definition** (no funding exists), break-even as today. Futures adapter: fees from `FuturesCommissionRateReader`, funding from a new `IFundingReader`.
- [ ] `IFundingReader` (a trading contract, Futures adapter reading the funding rate and next funding time; Spot answers `NotApplicable.ON_THIS_VENUE`) and `FundingRate(symbol, rate, next_funding_at, as_of)`.
- [ ] The Futures plan checks use the Futures fees: `check_min_step` / `check_break_even` (same thresholds, same codes) with `2 × fee` from the account; a new `FUNDING_ADVERSE` WARNING when the current funding rate costs the plan's net direction more per 8 h than a stated share (default 25 %, in `FuturesGridThresholds`) of its expected cycle profit.
- [ ] **PnL and progress for a Futures bot** count: realized profit per closed cycle (from the fills or the stream's realized-profit field), commissions (quote asset), and funding paid/earned (from the wallet events, labelled `reason = FUNDING_FEE` once its name is verified). `BotProgress` (`contracts/bot_progress.py`) gets the fields, with the Spot ones untouched; funding is shown separately from grid profit ("Grid profit is the sum of completed cycles; funding is separate", Pionex's split).
- [ ] No fee is counted twice: the fee on a fill reaches PnL from exactly one source (the fill report **or** the trade list), with the dedup key decided in 039D.
- [ ] Spot PnL and progress numbers are **unchanged** for the Spot oracle inputs (`039B`'s fixture).

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
- `test_futures_fees_come_from_the_account_and_set_the_break_even_step`
- `test_a_position_across_a_funding_time_pays_or_earns_and_progress_shows_it_separately`
- `test_an_unreadable_funding_rate_is_unknown_not_zero`
- `test_funding_adverse_warns_when_it_eats_the_cycle_profit`
- `test_a_fill_fee_reaches_pnl_once_whichever_report_comes_first`
- `test_spot_pnl_is_unchanged_for_the_oracle_inputs`
Not run yet.

## Pitfalls
- A fee in the **base** asset exists on Spot only; the Spot sizing rule "net of the opening fee" must stay behind the Spot adapter.
- Funding is a wallet event (`ACCOUNT_UPDATE` reason), not a fill: counting it in the grid's realized profit would hide a losing grid behind a funding gain.
- Rates differ by account tier; never hard-code 0.02 %/0.05 % (those figures in the owner's chat were from memory).

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: read Binance's order-update and account-update event pages (`llms-full.txt` if the pages do not render) and record commission, `rp` and the funding reason name here.
