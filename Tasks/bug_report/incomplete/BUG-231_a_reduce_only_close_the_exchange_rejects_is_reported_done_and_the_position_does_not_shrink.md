# BUG-231 — Exit slice 1 reports `done` but the position does not shrink, and the exchange rejects a reduce-only close of the whole position

- **Reported:** 2026-10-19 (coordinator session, from the owner's VPS journal and Binance testnet screenshots; bot `e2zeyr`, BNBUSDT)
- **Severity:** 🔴 P1. A stop that closes a leveraged position can believe it sold what it did not.
- **Status:** Open
- **Board:** Exit slice 1 of 0.66 BNB was logged `done`, yet the derived position stayed 3.96 and the exchange UI refuses a reduce-only close ("ReduceOnly Order is rejected") for both open positions even with no open orders. Not reproduced; cause not established.
- **Context:** `bots` → `application/kinds/grid/stop/grid_exit_slices.py` (`send_exit_slices`), `application/services/positions/closer_futures.py` (`PositionExposureCloser.close`) → `trading` order submission
- **Environment:** VPS, Futures Testnet, isolated 5x, 2026-10-19 15:38 UTC, `159fbfd`.

## Reproduction
Not yet reproduced on the fake exchange.

## Symptom
Journal: `Live order submitted ... SEW-e2zeyr-5133cbc7f8`, `exit slice 1 of 0.66 -> done`; at 15:38:16 the derived position is still 3.96 with `0 fill(s) from a checkpoint`, and no fill or cancel event of the bot reached the log. Screenshots: Positions BNBUSDT Long 3.96 @726.541 and ETHUSDT Long 0.308, Open Orders(0), and `Close Positions Failed: ReduceOnly Order is rejected` for both (the exchange's own UI close, also the ETH position of bot puhy4o). Earlier the same day reduce-only orders worked on ETH and a BTC halt-close worked on this venue.

New fact (owner, 2026-10-19): closing the BNB position on the testnet by a LIMIT order works; the reduce-only MARKET close is what the exchange rejects. The bot closes only with reduce-only market slices (`BotOrderGateway.market_reduce_only`), so on this testnet its own close cannot succeed.

## Root cause
Not yet established. By reading: a slice is `done` when the submit is accepted (`classify_submit`), not when it fills; the stop confirms a close only by reading the position after all slices (`PositionExposureCloser._confirm`), and a halt at slice 2 (BUG-228) never reached that read. The rejection may be an exchange-side condition on these two positions that no resting order explains.

## Suggested next steps
Owner's Binance Order History status of `SEW-e2zeyr-5133cbc7f8` and a Limit close / plain Sell of the exact size (relayed by the coordinator). Then: reproduce a reduce-only market order the exchange accepts and later rejects (fake fault), and make the stop surface it as a named refusal carrying the exchange's reason, not as `done` or as a budget halt.

## Start-side evidence and what the code covers (owner's journal, 16:13 UTC)
After both bots were stopped with the close option (both reached STOPPED) and started again: the opening market slices fill (ETH 0.308, BNB 3.96), the protective stop stands, then the first ladder order, a reduce-only LIMIT SELL, is refused with `APIError(code=-2022): ReduceOnly Order is rejected.` 0.6 s later; the bot goes to ERROR and the halt's market reduce-only slice is refused with the same code. The same ladder started at 12:43 UTC (60 reduce-only sells and 2 conditional stops together) and the exchange UI's own Market close was refused at 15:40 UTC while its Limit close worked.

What the code covers, read at `159fbfd` (not run on the exchange):
- Reads: the Futures client's `get_open_orders` returns regular and algo (conditional) orders together, and every owner/bot read goes through it (`futures_trading_client.py` → `get_open_orders`); `BotAccountReads` splits them by `close_position` (`ladder_orders`, `protective_orders`). The cancel falls back to the algo endpoint on `-2011` (`cancel_order`). So an earlier run's protective stop with the bot's tag is listed and cancelled (`ProtectionFutures._cancel_untracked`); a stop with another tag is not the bot's and is not listed as its own. `Owner budget registered ... 0 open order(s)` counts the bot's tagged orders of both kinds, so it does not show foreign conditional orders.
- Position mode: hedge mode is refused when the order session opens (`HEDGE_MODE_UNSUPPORTED`), but only at that check; a switch afterwards is not re-read before each order.
- Nothing in the code can make a reduce-only order refused on its own when it reduces an existing position; the exchange's rule is not documented in a source I could retrieve (a web search found no authoritative Binance text for `-2022`; the Binance USD-M futures error-code page is the source to read).

Candidate causes, ranked by what the journal supports (all unverified on the exchange):
1. An exchange-side state of these two positions or of the account (position mode switched to hedge, the position not yet or no longer what the matching engine sees, margin mode), supported most: the exchange's own UI Market close was refused with no resting order and a Limit close worked, so our orders are not the cause.
2. A standing order that commits the position (a reduce-only or closePosition order on the exchange the bot did not list): not supported, the UI showed Open Orders(0) at 15:59 yet the close was still refused.
3. A defect in our order parameters (`reduceOnly` with `positionSide` or `closePosition`): not supported, the same orders were accepted at 12:43 and nothing in the code sends `positionSide`.
The check for the owner: the testnet's position mode (one-way vs hedge) and margin mode on both symbols, and the Conditional tab, at the time of the refusal.

## Diagnostic the bot lacks (proposed, not built here)
On every `-2022` and when the order session opens, log at INFO/WARNING with a tag: the account's position mode and margin type, and the refused order's `reduceOnly`, `positionSide`, type, price and quantity, plus the exchange's full error body, so the next incident names its cause in one run (`logging-rule.md`: log what is in effect). Today only the exception type reaches the bot's reason text.

## Proposal (an owner decision on the money path; not built in PR 579)
When the exchange refuses a reduce-only market close, the stop must at least surface the exchange's reason as a named failure (the refusal reason is already translated, `REDUCE_ONLY_REJECTED`, but a refused slice currently halts with a generic `exit_slice_failed` text), never `done` and never a budget halt. Whether to fall back is the open question:

| Option | For | Against |
| :--- | :--- | :--- |
| A. Surface the named refusal only; the owner closes by hand | No new order path on a leveraged position; smallest change | The position stays open until a human acts; a halt that "closes" does not close |
| B. Fall back to an aggressive reduce-only LIMIT at the opposite touch, then re-read the position | Closes where the market close is refused (the owner's LIMIT close worked); still reduce-only | A limit can rest unfilled and needs a re-price loop and a cancel; slippage; a second order path to test on the real venue |
| C. Fall back to a plain non-reduce-only order | Most likely to be accepted | Can open the opposite side if sized or timed wrong: rejected, it is the one the reduce-only flag exists to prevent |

Recommendation: A now (named refusal, alert to the owner), B as a separate, reviewed task once the Order History of the refused slice shows why the market close is rejected; never C.
