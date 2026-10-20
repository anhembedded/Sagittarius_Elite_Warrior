# BOT-202 — Total PnL says what it is: net of fees, at the bot's last trade price

**Status:** ✅ Done (2026-10-20)
**Priority:** P2
**Board:** The owner's "PnL does not match the exchange" is not a defect: the bot's Total PnL is net of fees and funding at its last 1-minute close while Binance's position PNL is gross at the mark price; the Bots tab, `bot list` and `bot show` now say so in words built once, `bot show --json` carries commissions, funding, cost and the price's time, `bot show` says the exchange-basis unrealised is not available (the mark price is not saved), and the Discord cycle line says "grid profit" (`BotOrderFilledEvent.grid_profit`); no figure changed.
**Source:** the owner, 2026-10-20, from the VPS: "is this a bug? the PnL does not match the exchange; also check similar bugs" (bots `puhy4o`, `e2zeyr` on Futures Testnet, `uie03d` on Spot Mainnet). Investigated by a session of the coordinating session `session_016sGQHsRy729Fp4cY1cTXfu`.
**Risk:** 🟢 — wording and report fields only; no figure changes.
**Complexity:** S — three display sites, one payload, their tests.
**Depends on:** None.

---

## 1. Context and problem

### Verdict: (a) correct by definition, labelled ambiguously
Nothing in the evidence shows a wrong price, a doubled fee, a wrong sign or a wrong quantity. The two figures measure different things. One premise is inferred and needs the owner's data to be proven (§1.3).

### 1.1 How the bot's figure is made (commit `a6d950a`)
| Part | Rule | Where |
| :--- | :--- | :--- |
| Total | `realised_total + unrealised + funding_total`; `None` (shown "no price yet") while no price was heard | `src/modules/bots/domain/grid/grid_pnl.py` → `pnl_summary` |
| Unrealised | `inventory × (mark_price − average_cost)` | `grid_pnl.py` → `_unrealised` |
| Average cost | `cost / abs(inventory)`; for a long, `cost` **includes** the quote fee of every buy (`price × quantity + quote_fee`), so the opening fee is already in the cost basis; for a short the fee is taken off the proceeds | `src/modules/bots/domain/grid/grid_books.py` → `_deepen`, `book_inventory`; `GridRuntime.average_cost` |
| Fee | the fill's own commission from the trade report: quote asset as paid, base asset (Spot) leaves the inventory, a third asset (BNB) is priced in the quote asset at the fill; one that cannot be priced is counted in `unpriced_fees`, never guessed. Taker or maker is whatever the exchange charged; nothing is assumed | `src/modules/bots/application/kinds/grid/grid_fill_conversion.py` → `GridFillConversion.level_fill`, `_fee_in_quote` |
| Funding | settled funding events of the symbol, signed, inside the total and outside the grid profit | `grid_facts.py` → `GridFacts._apply_funding`; `GridRuntime.with_funding` |
| Price | **not** the mark price and not the book: the close of the venue's own 1-minute kline stream (`candle.close_price`), i.e. the last trade; on Futures Testnet the testnet stream (`TradingVenue.market_data_venue`, `BUG-172`) | `src/modules/bots/application/event_handlers/bot_event_router.py` → `BotEventRouter.on_tick` |
| Refresh | saved with the bot's state at most every `MARK_PRICE_SAVE_SECONDS = 30.0` of the bot's clock; `bot list`, `bot show` and the Bots tab read that saved file, so the figure is up to 30 s older than the tick it came from, and as old as the file when the bot is not running | `src/modules/bots/application/kinds/grid/watch/grid_price_reaction.py` → `GridPriceReaction._save_mark_price`; `bot_progress_reader.py` → `bot_progress` |
| Exits | a Futures stop loss and take profit are judged on the **mark** price (`on_mark`); the PnL uses the last trade. Two prices on purpose | `grid_price_reaction.py` → `on_mark`, `on_tick` |

Binance's Positions-tab PNL is `size × (mark − entry)`: gross of fees, funding excluded, at the **mark** price (the default of the tab).

### 1.2 Reconciliation of the two Futures rows
Binance's own break-even minus entry is 0.960 on ETH (0.0399 % of 2,408.24) and 0.292 on BNB (0.0400 % of 730.22): its estimate of the fees of a round trip is 0.04 % of the notional.

| | ETH `puhy4o` | BNB `e2zeyr` |
| :--- | ---: | ---: |
| Notional at entry | 0.297 × 2,408.24 = 715.28 | 3.78 × 730.220 = 2,760.23 |
| Binance PNL, recomputed `size × (mark − entry)` | 0.297 × 4.57 = **1.357** (shown 1.37) | 3.78 × 0.653 = **2.468** (shown 2.49) |
| Bot Total PnL | **1.07** | **1.50** |
| Gap (Binance − bot) | 0.30 (0.042 % of notional) | 0.99 (0.036 % of notional) |
| Opening fee at 0.04 % of notional | 0.286 | 1.104 |
| Prediction `Binance − 0.04 % fee` | 1.357 − 0.286 = **1.071** (bot 1.07, residual 0.00) | 2.468 − 1.104 = **1.364** (bot 1.50, residual +0.136) |
| Residual as a price difference | none | +0.036 per BNB (bot's last trade 0.036 above the mark of the screenshot) |

The ETH row agrees to the cent. The BNB residual is 0.036 USDT per coin, 0.005 % of the price: the difference between the last trade of a 1-minute close up to 30 s old and the mark price on a thin testnet book. Both gaps are the opening fee and nothing else; cycles are 0 and grid profit is 0, so no sell has been booked, and funding was assumed 0 (a testnet funding of 0.01 % would be 0.07 on ETH and 0.28 on BNB, which the BNB residual could hide).

A first reading ("0.99 is more than the opening fee alone") compared the BNB gap with 0.55, a maker-rate fee. At 0.04 % the opening fee is 1.10 and the gap is explained.

### 1.3 What is inferred, and the data that proves it
The 0.04 % opening fee is inferred from Binance's break-even, not observed. It is proven or refuted by, for each of the three bots:
- The bot's state file `runtime` (the keys of `grid_runtime_codec.py` → `encode_runtime`): `inventory`, `cost`, `commissions`, `funding_total`, `realised_total`, `mark_price`, `mark_price_at`, `unpriced_fees`. From these: opening fee = `cost − inventory × entry`; `commissions` is the fees paid.
- The Bots tab's detail panel for the bot (rows "Commissions paid", "Funding", "Last price heard", "of which unrealised"), which shows the same.
- Binance **Trade History** for the symbol: the `Fee` column of the opening market order(s).

`bot show --json` does **not** carry `commissions`, `funding`, `cost` or `mark_price_at` (`bot_status_report.py` → `_earnings_payload`), so it cannot settle this alone.

The Spot bot `uie03d` (TOTAL PNL 0.20) cannot be reconciled: Binance Spot shows no position PNL and the owner gave no figure. The Spot rule is the same books with the fee taken from the base asset (`grid_books.py` → `book_inventory`: `inventory + quantity − base_fee`, `cost + price × quantity + quote_fee`), so its total is also net of fees.

### 1.4 Similar figures checked
| Place | Finding |
| :--- | :--- |
| Bots tab columns | "Total PnL" and "Grid profit" are the same rules as `bot list`, built once in `run_earnings.py` → `RunEarnings`. The plan panel already adds "of which unrealised", "Commissions paid", "Funding" and "Last price heard" (`bot_plan_panel.py`). No mismatch beyond the label. |
| `bot list` / `bot show` | The same figures. `bot show` has "Unrealised … at <price>" (`unrealised_text`) but no commissions, no funding and no age of the price; the table head says only `TOTAL PNL`. |
| Discord fill and cycle message (`BOT-189`) | **Mismatch of words.** The cycle line prints `total +X`, but `X` is `FilledOrder.realised_total = after.realised_profit` (`grid_filled_order.py`, `filled_order`): the run's **grid profit**, not `GridRuntime.realised_total` and not the Total PnL. A run that sold its opening inventory or an exit slice has a different Total PnL than this "total". `BotOrderFilledEvent.realised_total` carries the same grid profit under a name `GridRuntime` uses for another figure. |
| Grid profit per cycle | `book_cycle` is `spread × quantity − exit fee − the entry's fee`, net of both legs; the Total PnL books the same fees through the average cost. Consistent by construction; not compared against fills here (no cycle in the owner's evidence). |
| Spot vs Binance Spot | See §1.3: not comparable without the owner's figure. |
| Budget and exposure checks | `bot_progress.py` states the run's account is "never a safety input"; `grid_budget.py` and `grid_budgets.py` read no PnL, mark or realised figure (grep `pnl\|mark\|realised`: no hit). Not affected. |

## 2. Acceptance criteria
- [x] The Bots tab column, `bot list` head and `bot show` line for the total say it is net of fees and funding at the bot's last trade price (the exact words are the implementer's, one place: `run_earnings.py`).
- [x] `bot show` gives, for a Futures bot, the exchange-comparable unrealised (`inventory × (mark − entry)`, gross, at the mark price) beside the net one, or says it cannot because no mark was heard; both labelled.
- [x] `bot show --json` carries `commissions`, `funding`, `cost` and `mark_price_at` of the run, as exact decimal text.
- [x] The Discord cycle line names what its running figure is ("grid profit"), or carries the Total PnL; `BotOrderFilledEvent.realised_total` is renamed to say grid profit, or documents that it is not `GridRuntime.realised_total`.
- [x] No figure changes: the unit tests that pin the totals pass unchanged.

## 3. Design
Wording and report fields, built where the words already live (`RunEarnings`, `unrealised_text`), so the desktop and the commands change together (the reason `BOT-192` built them once). The owner's data (§1.3) is requested before the exact fee premise is written into any text; the wording itself does not depend on it.

## 3a. Reuse
`RunEarnings` and `unrealised_text` of `run_earnings.py`; `plain_money`, `plain_price`, `money_text` (capability catalog: "Write a price or money amount as text without Qt"); `_earnings_payload` for the JSON.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/run_earnings.py` | total and unrealised words; the exchange-comparable unrealised |
| `src/modules/bots/contracts/bot_status_report.py` | the four payload fields |
| `src/modules/bots/cli/bot_status_reports.py` | the head and the `bot show` lines |
| `src/modules/bots/ui/bots_screen/bots_table_models.py`, `bot_plan_panel.py` | the column and row titles |
| `src/modules/alerting/application/sources/bot_fill_alert_source.py`, `src/modules/bots/contracts/events/bot_order_filled_event.py` | the word "total" |

## 5. Testing
Unit tier: the report and the panel text for a run holding base (net total, comparable unrealised at the mark, the JSON fields); the cycle line wording; an existing total test unchanged (criterion 5). Not run in this documentation-only change.

## 6. Docs touched
`Docs/SPEC/` use case of the bots list and show, if it quotes the head `TOTAL PNL`; the file is named when the task starts.

## Implementation notes (written when done)
- **Words, once** (`run_earnings.py`): `TOTAL_PNL_BASIS` ("net of fees and funding, at the bot's last trade price"), `TOTAL_PNL_TITLE` (Bots tab column "Total PnL (net)"), `TOTAL_PNL_HEAD` (`bot list` head `TOTAL PNL (NET)`) and `TOTAL_PNL_LEGEND` (one line under the `bot list` table, so the head stays short; BOT-198 wrapping is unaffected). The Bots tab's detail row reads "Total PnL (net of fees and funding, at the bot's last trade price)"; the column itself carries the short title only. `bot show` keeps the label `Total PnL` and prints the basis on the line under it, so the existing label-and-value tests pass unchanged.
- **Exchange basis, criterion 2 resolved as "cannot".** The reader of `bot show` has only the saved run, and the saved price is the last trade price (the 1-minute close), never the mark price; the mark is heard live and not stored. Quoting `inventory x (price - entry)` at the last trade price would be a figure at a price the exchange does not use, and the entry price is not recoverable exactly from `cost` (a long's cost holds the opening fee). So a Futures bot's `bot show` prints `Unrealised, exchange basis` followed by "not available: the bot saves its last trade price, not the exchange's mark price" (`exchange_unrealised_text`); a Spot bot prints no such row. Saving the mark price with the run would be a state change and is not part of this task.
- **JSON** (`_earnings_payload`): `commissions`, `funding`, `cost` as exact decimal text (`commissions` and `funding` `null` when the run was not judged) and `mark_price_at` as UTC text, `null` before a price was heard. The test that pinned the key set gains the four keys; no existing value changed.
- **Discord**: the cycle line reads `grid profit +12.80 USDT`; `BotOrderFilledEvent.realised_total` and `FilledOrder.realised_total` are renamed `grid_profit` (they were `GridRuntime.realised_profit`, while `GridRuntime.realised_total` is another figure). The tests that built or read the field use the new name; no figure changed.
- **Not done:** the owner's data (§1.3) that would prove the 0.04 % opening-fee premise; no text states it as a fact.
- Docs: `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/OPERATIONS/headless_runbook.md`, `Docs/MODULES/bots/07-deployment.md`, `Docs/MODULES/alerting/05-building-blocks.md`.
