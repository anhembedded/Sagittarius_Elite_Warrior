# BUG-247 — Two wide Futures grids close the request-weight gate and every bot read then fails as an ERROR with a traceback

- **Reported:** 2026-10-20 (the owner's unattended Futures Testnet run on the VPS, through the delivery coordinator)
- **Severity:** 🟡 P2 — about every hour the app's own gate paused all requests for up to a minute, so the stop loss, take profit and protective-stop check of every running bot went unjudged meanwhile, and the pause wrote about 200 ERROR lines a day that hide real errors and fail the run-log scan
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** Cause: the order gate made a 7-weight connection check per order and cancel, so two wide ladders closed the weight gate; and a handled pause was logged as ERROR per bot read. Fix: a passing check is kept for 5 s; a pause is DEBUG for bot reads and one WARNING for the venue.
- **Context:** Run a grid bot (`Docs/SPEC/SPEC-014_run_a_grid_bot.md`) → `trading/application/orders/` (the order gate) and `bots/application/` (the reads that meet a pause) → application layer
- **Environment:** `sew-run` under systemd, `run --stop-timeout 25 --health-interval 60 --on-stop leave-orders --start-planned --resume-halted`, Futures Testnet, master `43bd4392` (2026-10-20 14:38 UTC). Measured here on the fake exchange at `d8b9b7c`.

## Reproduction
On the fake exchange (`tests/sanity/fake_exchange/`, weights as Binance documents them): two Futures grid bots of 48 and 83 levels started inside one minute with the real gate.
1. Before the fix the starts spend 1,682 weight (`account` 830, `positionRisk` 180, `time` 167, `ping` 166, `commissionRate` 120), reaching the gate's 1,680 line.
2. A pause met by two running bots on their beats writes `ERROR` lines (`the position of X could not be read` with a traceback) every beat.

## Symptom
From the owner's log (verbatim, abridged):
```
App.TradingAdapter - WARNING - Used weight 1778 of 2400: no request is sent for 9 s, until 15:00:01 [rate-limit-soft]
App - ERROR - GetMarkPriceQuery failed: ... the exchange asked for a pause
GridExecutor - ERROR - Bot X: the position of SYM could not be read      (full two-part traceback)
WARNING ... the protective stop is not looked at this time [protective-stop]
WARNING ... the mark price could not be read; stop loss and take profit are not judged until it can [mark-exit]
ERROR - Bot e2zeyr: the open protective stops could not be read [protective-stop]
```
About 24 h: 78 mark-price and 52 position ERRORs, 14–15 position ERRORs for each of the two bots that ran alone after the restart (about one pause an hour), 17 "account summary stale" and 16 "position refresh failed" WARNINGs.

## Root cause
Measured at `d8b9b7c` on the fake exchange.
1. **Weight.** Steady load is not it: two idle Futures bots with the 5 s position and account-summary refreshes spend about 630 weight a minute (26 % of 2,400). The burst is the order gate: `trading/application/orders/connection_gate.py` → `order_connection_block` ran a full `account_reader.check_connection()` (ping 1 + time 1 + account 5 = 7 weight, plus `positionSide` 30 once a minute) before every order and every cancel, both in `ExecuteOrderCommandHandler` and `CancelOrderCommandHandler`. A ladder sends one order per level, so laying 48 levels spent 760 weight (345 on `account`, 70 `time`, 69 `ping`) and 83 levels about 1,250; a halt recovery cancels every tagged order and lays a fresh ladder, paying it twice. The cap of 60 orders a minute and 250 ms spacing bound the rate, not the weight per order. Two bots laying together reach 70 % (1,680) late in a minute and the gate pauses every read until the minute ends (the `:52` of the log). The pause halts the bots, whose recovery re-lays the ladders (three recoveries per 24 h), which is why it came back about hourly. The VPS total of 1,778 is not reproduced exactly; its composition is measured, its sum inferred.
2. **Log level.** (a) `trading/adapters/binance/market_price_reads.py` → `market_price_answer` worded a paused mark read without `EXCHANGE_PAUSE_TAG`, so `PausedCallFailureFilter` (`shell/dispatch_log_filter.py`) did not demote the dispatcher's `GetMarkPriceQuery failed` ERROR. (b) `bots/application/services/orders/bot_account_reads.py` → `BotAccountReads.position` and `protection_futures.py` → `_open_stops` logged any failure with `logger.exception`, the pause included. (c) `ProtectiveStopService.supervise` told "the position could not be read" at WARNING on every beat.
3. **Safety consequence.** While the gate is closed no read is sent, so for every bot the stop loss, take profit and protective-stop check are not judged until the pause ends: up to the rest of the minute plus one second (the logged 9 s was the tail of a pause that began at :52; one that begins at :01 lasts 60 s), per bot, all bots together. The exchange-side protective stop order, already resting, still triggers on the exchange; the app's own exits and its replacement of a missing stop wait.

## Fix
- `trading/application/orders/order_connection_memory.py` (new), `connection_gate.py`, `venue_session_states.py`, `venue_trading_scope.py`: `order_connection_block` asks the venue's `OrderConnectionMemory`, which keeps a passing check for 5 s (one price-watch beat) and never keeps a failed or rate-limited one. The lock covers the memo, not the network read. This is the mechanism for every order and cancel on both venues, not a Grid-only patch.
- `market_price_reads.py`: a paused mark read carries `EXCHANGE_PAUSE_TAG`, so the existing dispatcher filter demotes its `failed:` line.
- `bot_account_reads.py`, `protection_futures.py` (logging lines only), `unread_streak.py` (new): a position or open-stops read refused by the pause is DEBUG; the "protective stop is not looked at" WARNING is told once per run of failed reads, not every beat.
- Not changed, by decision: when stops are judged (options B and C below).

## Regression test
Red before the fix, green after:
`tests/integration/modules/bots/test_two_wide_ladders_stay_inside_the_weight_gate_on_the_fake_exchange.py`, `test_a_pause_is_told_once_not_as_errors_on_the_fake_exchange.py`; unit: `test_order_connection_memory.py`, `test_rate_limited_error_of.py`.

## Verification
Fake exchange, 48 and 83 levels started in one minute with the real gate: 1,682 weight before (the gate's 1,680 line reached, a cancel refused with a 47 s pause), 862 after; `account`+`time`+`ping` 1,163 before, about 190 after. A pause met by two running bots on 6 beats wrote 12 ERROR lines (`the position of X could not be read`) before, none after; their WARNINGs no longer grow with the beats. Commit tier `ci-local.ps1 -SkipTests`: PASS. `tests/unit`+`tests/integration` (18,772 passed) and the architecture, bots, trading suites pass; `test_workbench_conformance[1024x700]` fails the same on master in this container. One existing test, `test_a_steady_state_order_costs_the_documented_minimum_of_requests`, changed: an order inside a beat now costs the order alone (1 request, was 6 on Spot).

## Next steps for the owner
Options for the stops during a pause, for the owner (the coordinator's decision: A now, C as a follow-up, B rejected):
- **A (built).** Avoid the pause by budget: the order gate no longer reads the account per order.
- **B (not built, rejected unless the owner asks).** Judge stop loss and take profit from the last known mark with an age bound. Changes real-money behaviour: an exit would fire on a mark the app did not just read.
- **C (follow-up for the owner).** A weight reserve above the 70 % line for the reads that guard exits (position, mark, open protective stops), so ladder placement waits and the guarding reads pass.
