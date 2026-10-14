# BUG-203 — A Futures Grid's own opening fills are logged as position divergence warnings at every start

- **Reported:** 2026-10-14 (the owner, coordinator session, first VPS run of a Futures Grid on Futures Testnet)
- **Severity:** 🟢 P3. The bot started and reconciled correctly, so there is no trading harm. Every start writes about five WARNING records that cry wolf. Once an alert channel exists (`EPIC-036`) they would page the owner, and the run-log scan treats WARNING as a failure in CI.
- **Status:** Open
- **Board:** A Futures Grid's start logs its own opening fills as "position_mismatch / position_changed_unordered — exchange wins" warnings, then re-reads and finds nothing wrong
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), starting a Futures Grid → `trading` (`LiveTradingCoordinator`, owner position book) and `bots` (`GridExecutor` divergence watch) → `application/`
- **Environment:** VPS, Ubuntu 24.04 (KVM, systemd 255), headless host `run --start-planned`, `master-warrior` at or after `64e5510`, Futures Testnet, ETHUSDT, LONG, leverage 2, 8 levels

## Reproduction
1. Apply a plan with one Futures Grid on `futures_testnet`, `desired_state` running.
2. Start the host with `--start-planned`.
3. Read the journal during the opening.

Expected: the opening's market fills are attributed to the bot as they arrive. No WARNING is written, because nothing foreign happened.

Actual: one WARNING per opening fill, a "re-reading in 5 s before acting" per fill, then "the position agrees again after the re-read; left running".

Frequency: seen once, on the first start; not yet re-run.

## Symptom
```text
14:28:56,491 App.LiveTradingCoordinator - WARNING - Position position_changed_unordered for goy5j8 on ETHUSDT: derived 0, exchange reports 0.079 — exchange wins [position-divergence]
14:28:56,498 App.CommandHandler - INFO - Live order submitted on futures_testnet: ETHUSDT SEW-goy5j8-108afc279f
14:28:56,581 App.LiveTradingCoordinator - WARNING - Position state mismatch for ETHUSDT: app believed flat, exchange reports open — exchange wins.
14:28:56,583 App.LiveTradingCoordinator - WARNING - Position position_mismatch for goy5j8 on ETHUSDT: derived 0.079, exchange reports 0.144 — exchange wins [position-divergence]
14:28:57,101 App.LiveTradingCoordinator - WARNING - Position position_mismatch for goy5j8 on ETHUSDT: derived 0.144, exchange reports 0.179 — exchange wins [position-divergence]
14:28:57,190 App.LiveTradingCoordinator - WARNING - Position position_mismatch for goy5j8 on ETHUSDT: derived 0.179, exchange reports 0.259 — exchange wins [position-divergence]
14:28:57,279 App.LiveTradingCoordinator - WARNING - Position position_mismatch for goy5j8 on ETHUSDT: derived 0.259, exchange reports 0.288 — exchange wins [position-divergence]
14:28:57,948 App.Bots.GridExecutor - INFO - Bot goy5j8: opening counted from the exchange's record: a position of 0.288, the ladder sells 0.288 [position-opened]
14:29:03,127 App.Bots.GridExecutor - INFO - Bot goy5j8: the exchange's position 0.079 differs from the bot's 0 (position_changed_unordered); re-reading in 5 s before acting [position-divergence]
   (four more re-read lines, one per fill)
14:29:12,632 App.Bots.GridExecutor - INFO - Bot goy5j8: the position agrees again after the re-read; left running [position-divergence]
```
The "exchange reports" values step through the opening's own fills (0.079 → 0.144 → 0.179 → 0.259 → 0.288). In each line the derived figure lags exactly one fill behind.

## Root cause
Not yet established. Hypothesis, unverified: Binance sends the position change (`ACCOUNT_UPDATE`) before the fill (`ORDER_TRADE_UPDATE`) that caused it. The divergence check compares the exchange's new position with a derived position that has not yet applied that fill. It flags the bot's own fill as an unordered change one step before the fill arrives. The fake exchange (`EPIC-039C`) may send the two in the other order, which would explain why no test saw this.

## Fix
Not started.

## Regression test
Not written. It belongs at the tier where the order of the two stream events is controlled: the Futures fake exchange, with a fault that sends `ACCOUNT_UPDATE` before `ORDER_TRADE_UPDATE`.

## Verification
Not run.

## Suggested next steps
- Confirm the event order from the raw user-stream log of a testnet start (DEBUG on the stream adapter).
- Make the fake exchange able to send the position update first. Check whether the 039D duplicate and out-of-order faults already cover this.
- Fix at the mechanism. While the bot's own order on that symbol is still unfilled or only partly filled, a position change is a pending fill, not a divergence. Settle it by the next fill, or by the existing 5-second re-read without a WARNING. Never by widening a tolerance.
- Also check the coordinator's separate "app believed flat, exchange reports open" WARNING for the same race.
