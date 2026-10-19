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

## Root cause
Not yet established. By reading: a slice is `done` when the submit is accepted (`classify_submit`), not when it fills; the stop confirms a close only by reading the position after all slices (`PositionExposureCloser._confirm`), and a halt at slice 2 (BUG-228) never reached that read. The rejection may be an exchange-side condition on these two positions that no resting order explains.

## Suggested next steps
Owner's Binance Order History status of `SEW-e2zeyr-5133cbc7f8` and a Limit close / plain Sell of the exact size (relayed by the coordinator). Then: reproduce a reduce-only market order the exchange accepts and later rejects (fake fault), and make the stop surface it as a named refusal carrying the exchange's reason, not as `done` or as a budget halt.
