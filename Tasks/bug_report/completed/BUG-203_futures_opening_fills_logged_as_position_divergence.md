# BUG-203 — A Futures Grid's own opening fills are logged as position divergence warnings at every start

- **Reported:** 2026-10-14 (the owner, coordinator session, first VPS run of a Futures Grid on Futures Testnet)
- **Severity:** 🟢 P3. The bot started and reconciled correctly, so there is no trading harm. Every start writes about five WARNING records that cry wolf. Once an alert channel exists (`EPIC-036`) they would page the owner, and the run-log scan treats WARNING as a failure in CI.
- **Status:** ✅ Fixed (2026-10-19)
- **Board:** A Futures Grid's start logged its own opening fills as "position_changed_unordered — exchange wins" and "app believed flat" WARNINGs, then re-read and found nothing wrong. Cause: the two `LiveTradingCoordinator` lines warn on a snapshot (the account's report outrunning the fill; a budgeted owner's order never marking the symbol open) that the owner's re-read has yet to confirm. Fix: they log at DEBUG; the confirmed divergence is still warned about by the registration and the watch.
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
Established on the Futures fake at `159fbfd`; the raw VPS stream was not read, so *which* of Binance's two reports comes first is still unproven on the exchange itself (the fake and `BUG-216`'s test deliver either order and the app handles both).

Two WARNINGs, both on a snapshot rather than a confirmed fact:
1. `position_state_reconciler.py` → `cross_check_owner_positions` warned on every `OwnerPositionDivergedEvent` the moment the `ACCOUNT_UPDATE` was handled. The account's report outruns the `ORDER_TRADE_UPDATE` that explains it (`BUG-216` made the book answer from the stream's last figure), so for the seconds between them the derived position lags by one fill and the book reports it. The grid watch (`grid_risk_watch.py` → `_confirm_divergence`) already treats that report as unconfirmed: it re-reads after `position_recheck_delay` and halts and warns only if it still differs. The trading-layer WARNING pre-empted that decision for every fill of an opening (the five lines).
2. `position_state_reconciler.py` → `reconcile_position_state` warned "app believed flat, exchange reports open" on the first report of a position. A budgeted owner's order never marks the symbol open (`execute_order/handler.py`, "it neither marks the symbol open"), so the session's `known_open_symbols` can only learn an owner's position from the exchange. The belief was not wrong, it was never held, so this fired at every start of every Futures bot.

## Fix
- `cross_check_owner_positions` logs the unconfirmed divergence at DEBUG (one line per fill of a burst). The event, the cross-check, the once-per-cause rule and the tolerance are unchanged; a confirmed divergence is still warned about by the registration's re-read (`App.Trading.OwnerPosition`) and by the watch's halt.
- `reconcile_position_state` logs a correction on a symbol a budgeted owner trades (`OwnerBooks.has_owner_on`, new) at DEBUG; on any other symbol it still warns.
- Neither the owner-budget, the exposure nor the reduce-only checks are touched.

## Regression test
- `tests/integration/modules/bots/test_an_opening_fill_the_account_reports_first_logs_no_warning_on_the_fake_exchange.py`: a Futures Grid opening whose fills the account reports first writes no WARNING; a position opened by hand still produces the `[halt-closes-position]` WARNING and halts the bot. Red before the fix (two extra WARNINGs: the divergence and "app believed flat"), green after.
- `tests/unit/modules/trading/application/test_position_state_reconciler.py`: a budgeted owner's symbol learns its position silently; another symbol still warns.

## Verification
The two tests above, red-before/green-after on this commit; the existing `BUG-216` ordering tests pass unchanged. Not run on a live testnet: the order of the two stream reports on the exchange stays unconfirmed, and the fix does not depend on it.

## Suggested next steps
None for this report. When a testnet run is next read, confirm the raw order of `ACCOUNT_UPDATE` and `ORDER_TRADE_UPDATE` (DEBUG on the stream adapter) to retire the hypothesis in `owner_position_book.py`'s docstring.
