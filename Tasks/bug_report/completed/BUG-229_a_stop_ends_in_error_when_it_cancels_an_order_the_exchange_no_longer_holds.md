# BUG-229 — A stop ends in ERROR (`order_failed: cancel ...: OrderRejectedByExchangeError`) when it cancels an order the exchange no longer holds

- **Reported:** 2026-10-19 (coordinator session, from the owner's VPS: bot `e2zeyr`, 15:38:29 UTC, 27 s after BUG-228's halt)
- **Severity:** 🔴 P1. The cancel's goal (the order no longer rests) was met, yet the bot went to ERROR, so the stop never finished by itself.
- **Status:** ✅ Fixed (2026-10-19)
- **Board:** The stop went to ERROR on `cancel SEW-e2zeyr-...: OrderRejectedByExchangeError`. Cause: Binance's `-2011` "unknown order" answer became a `FAULT`, which ends the stop, though it means the order already ended. Fix: it is `OrderOutcomeKind.GONE`, counted as cancelled by the ladder's housekeeping.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (stop a grid bot) → `bots` → `application/services/orders/` (`BotOrderGateway.cancel`), `application/kinds/grid/grid_housekeeping.py`; `trading` → `adapters/binance/binance_error_translator.py`
- **Environment:** VPS headless, Futures Testnet, `159fbfd`. Reproduced on the fake Futures exchange.

## Reproduction
Same test file as BUG-228: with the lagging list, a second stop (BUG-228's halt closes the position by itself and stops again) lists the cancelled orders and cancels them again. Before the fix: `STOPPING -> ERROR on fault (order_failed: cancel SEW-...: the request failed (OrderRejectedByExchangeError); see the log)`, the owner's second alert.

## Symptom
Owner's second alert, 15:38:29 UTC: `Bot error ... Was STOPPING. Reason: order_failed (cancel SEW-e2zeyr-a90d094a71: the request failed (OrderRejectedByExchangeError); see the log)`.

## Root cause
`BotOrderGateway.cancel` (`bot_order_gateway.py:203` at `159fbfd`) turned every exception into `FAULT`; `translate_binance_error` had no name for `-2011`/`-2013`, so they were `UNKNOWN`. `GridHousekeeping._ended_meanwhile` (`grid_housekeeping.py:100`) forgives a FAULT only when a fresh read no longer lists the order, and the read that lagged is the one that listed it; `_ENDS_THE_STOP` (`grid_stop_sequence.py`) holds FAULT, so the stop ended in ERROR. The exception text was not in the owner's alert; `-2011` is inferred from the reproduction, **not read from the owner's journal** — the journal line would confirm it.

## Fix
`OrderRejectionReason.UNKNOWN_ORDER` names `-2011` and `-2013`; the gateway answers it with the new `OrderOutcomeKind.GONE` (not `DONE`, so a protective stop's record, which tells a cancel from an end, is unchanged); `_ended_meanwhile` counts GONE as ended. The stop then waits in STOPPING while the list still shows the order (never reported stopped early) and is retried.

## Regression test
`tests/integration/modules/bots/test_a_stop_that_closes_on_a_lagging_order_list_on_the_fake_exchange.py::test_a_cancel_of_an_order_the_exchange_no_longer_knows_leaves_the_stop_waiting_not_in_error` — red before (ERROR), green after; with only this fix reverted it fails on ERROR. Unit: `test_bot_order_gateway_close_and_cancel.py`, `test_binance_error_translator.py::test_an_order_the_exchange_does_not_hold_has_a_named_reason`.

## Verification
Regression tests green; the commit tier green. Partly addresses BUG-226 (the gateway no longer logs `raised` for an unknown order); that report stays open for the trading dispatcher's own ERROR line.

## Suggested next steps
None.
