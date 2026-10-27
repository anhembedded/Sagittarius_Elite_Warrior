# BUG-276 — A waiting Grid with a trigger price never sees a wick that touched the trigger

- **Reported:** 2026-10-27, by the owner (bot `ixr5v8` `BNB_ANH`, `futures_mainnet`, `BNBUSDT`, range 733–748, trigger `price <= 735`): "The bot not start even the price have pass through the trigger price."
- **Severity:** 🟠 P2 — the bot is safe (it places nothing), but it does not do what the owner's limit-style trigger promises; no money is lost, an entry is.
- **Status:** Open — design accepted by the owner 2026-10-27, implementation in slices ([the decision record](../../epics/EPIC-046_grid_trigger_price/DECISION_2026-10-27_a_triggered_entry_the_bot_cannot_miss.md))
- **Board:** A waiting futures Grid judges its trigger on one mark price read every 5 s, so a wick that touched the trigger between two samples (owner's 15m wick to about 734.7 under a 735 trigger) never opens it.
- **Context:** Use case run a Grid ([SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)) → `bots` → grid entry (`GridRangeEntry`, `GridPriceReaction`, `GridMarkExit`, `entry_gate`)
- **Environment:** App at `master-warrior` `b12b95f`; the bot's host is the owner's. The bot's log lines were not yet supplied.

## Reproduction
Not run. Observed by the owner: the Bots tab shows `AWAITING_RANGE` and "Waiting for the price ≤ 735.0000 within 733.0000–748.0000 (last price 737.8700, 12 s ago)". The owner's TradingView 15m chart (BNBUSDT, last-trade candles) shows one candle whose lower wick went to about 734.7, under the 735.00 trigger line, and the price closing back near 737.34 afterwards.

## Symptom
The price traded at or below the trigger, inside the range, and the bot kept waiting. Expected by the owner: "activate like a limit order", at the trigger or better.

## Root cause
Established from code at `b12b95f`; the wick's exact timing against the bot's samples is **not yet established** (needs the bot's `[range-wait]`, `[range-entry-deferred]`, `[price-poll]` lines near 07:3x UTC):
1. The gate is the band `[lower, trigger]` = 733–735 (`grid_entry_gate.py` → `entry_gate`), judged on **one sampled price**, never on what the price did between samples.
2. On a position venue the streamed kline tick is not offered to the entry: `grid_price_reaction.py` → `GridPriceReaction.on_tick` (`if not self._exits_on_mark`, line 138). The entry sees only the mark that `grid_mark_exit.py` → `GridMarkExit.check` reads over REST every `CHECK_EVERY_SECONDS = 5` (`bot_price_watch.py`) and wraps as `PriceTick.at(mark)` (line 51), a tick with no low or high.
3. The sample is then confirmed by a fresh book price (`grid_range_entry.py` → `GridRangeEntry._attempt`, line 157) that must still be inside the band, else the entry is deferred 30 s.
4. The chart is last-trade; the gate on a position venue is the mark (ADR 046 D2).
Spot has the same shape: `on_tick` passes `tick.last` only, so the kline low is discarded there too.

## Fix
Pending the owner's decision on what "activate like a limit order" means when the price touched the trigger and moved away. See the decision record: sampling alone cannot meet it.

## Regression test
Pending: a waiting LONG bot whose price path dips to the trigger and returns between two samples must, per the decided rule, either enter at the trigger or stay waiting with the dip shown.

## Verification
Not run.

## Suggested next steps
Owner answers the decision record's open questions in the author session; the bot's log lines and the exact wick time are requested.
