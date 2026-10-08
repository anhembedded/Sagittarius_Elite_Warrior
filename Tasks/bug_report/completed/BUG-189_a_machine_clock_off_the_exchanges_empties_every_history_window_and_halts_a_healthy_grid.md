# BUG-189 — A periodic reconcile halts a healthy Spot Grid: "saved 0.0119 against 0 derived from the exchange"

- **Reported:** 2026-10-08 (the owner, Spot Mainnet `ETHUSDT`, bot `g3n092`, master at `7451d3c`; via the coordinator session)
- **Severity:** 🔴 P1 — every Start on an affected machine ends in a HALT and a cancelled ladder about five minutes in, once `EPIC-035B` runs the gap reconcile. Funds are safe (the base stays in the account).
- **Status:** ✅ Fixed (2026-10-08)
- **Board:** The gap reconcile derived 0 inventory for a bot that held its opening buy and halted it. Cause: the history readers sent the machine's `run_started_at`, `now` and checkpoint `read_from` to Binance as they were and read back Binance's own stamps; the owner's clock is not Binance's (`BUG-111`), so every window opened after the bot's own first orders. Fix: the readers translate both ways by the offset the signed session measured ([CS-008](../../Docs/CASE_STUDIES/CS-008_the_clock_the_fake_never_had.md)).
- **Context:** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → trading (`src/modules/trading/`) → `adapters/binance/` (the history readers), seen through `application/owner_inventory_deriver.py`
- **Environment:** Windows, Spot Mainnet; master `7451d3c`. Reproduced on Linux against the fake exchange with its clock set 90 s and 20 s away from the machine's.

## Reproduction
1. A machine whose clock is not Binance's (here: 90 s fast, or 20 s slow).
2. Start a Spot Grid; it registers its budget, buys the opening slice and lays the ladder.
3. The venue's stream reports `CONNECTED` (or the 300 s check comes due): `GridStreamGap.reconcile` runs twice.

Expected: RUNNING, inventory unchanged. Actual: HALTED, `inventory_mismatch: saved 0.02397600 against 0 derived from the exchange`.

## Symptom
The owner's log: `Derived inventory for g3n092 on ETHUSDT: 0 ETH at cost 0 (from a checkpoint, 0 order(s)).` twice, then `RUNNING -> HALTED on halt (inventory_mismatch: saved 0.01188810 against 0 derived from the exchange)` and six cancels. The bot's own figure was right.

## Root cause
Two clocks compared as one. `run_started_at` (`SystemBotClock`), the deriver's `now` (`register_owner_budget/handler.py`), the checkpoint's `read_from` and the readers' `endTime` (`utc_now`) are the machine's. `allOrders.time` and `myTrades.time` are Binance's. `owner_inventory_deriver.py:113` reads `order_history(symbol, run_started_at)`: on a machine ahead of Binance by more than the seconds between the decision to start and the bot's first orders, the bot's own opening buy and ladder are stamped before the window opens, so no tagged order is read and the replay counts nothing. The first derivation at Start returned 0 too, which was harmless until `EPIC-035B` compared it with the bot's own figure every five minutes. The signed requests never noticed, since `BUG-111` made them carry the measured offset; the history windows did not. A machine behind Binance does the reverse: `endTime` falls before the newest fills.

Not observed: the owner's offset was not read from their machine. It is established that `BUG-111` was this machine's clock running fast, and that the symptom, the "0 order(s)" line and the red test below match; the two other leads (the 1-minute checkpoint overlap, the history cache) were ruled out: a 5-minute and 10-minute reconcile on a correct clock keep the inventory, and `discard_remembered` runs on the one registration path every caller shares.

## Fix
`SpotHistoryReader` and `FuturesHistoryReader` read the session's `timestamp_offset` (already measured for signing) and translate in both directions: the window sent is `since + offset .. now + offset`, and every time a record carries (`created_at`, `TradeRecord.time`, the order's `order_time`) comes back minus it (`history_reads.span_ms`, `from_ms`, `order_on_machine_clock`; the three mappers take `clock_offset_ms`). Callers keep one clock, so every consumer is covered: Start, Stop, resume, boot recovery and the gap reconcile through `derive`, the reconciler's `order_record` and `order_trades`, and the history tabs. `ISpotSessionClient` and `ITradingSessionClient` declare `timestamp_offset`; `IAccountHistoryReader` states the one-clock rule. `[clock-offset]` DEBUG logs the offset each time a session opens.

## Regression test
`tests/integration/modules/bots/test_a_machine_clock_off_the_exchanges_on_the_fake_exchange.py` (both skews): red before with the owner's message, green after. The unit pins are `test_history_readers_machine_clock.py`. The fake exchange now has a clock that can be skewed (`history_log.exchange_clock_skewed_by`) and answers `/time` with it.

## Verification
Red then green on the same test; `tests/unit/modules/trading`, `tests/integration/infrastructure`, `tests/integration/application`, `tests/integration/modules/bots` and `tests/unit/architecture` pass; the commit tier (`ci-local.ps1 -SkipTests`) is PASS. The full gate is the PR's `ci-local.ps1 -Full` check. Positive proof the new mechanism ran: with the machine 90 s fast the derivation counts the opening buy (`from a checkpoint, 8 order(s)` in the fake's log) where it counted none before.
