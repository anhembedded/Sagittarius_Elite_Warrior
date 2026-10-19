# BUG-226 — Cancelling a protective stop that is already gone after the position closed logs `ERROR ... cancel ... raised`

- **Reported:** 2026-10-19 (coordinator session, from the owner's VPS journal of the BUG-225 incident, bot `sj9rno`)
- **Severity:** 🟢 P3. The bot still ended STOPPED and flat; only the log level misleads.
- **Status:** ✅ Fixed (2026-10-19)
- **Board:** After a halt closed the position, cancelling the bot's protective stop (already gone) logged an ERROR. Cause: `BotOrderGateway.cancel`'s `logger.exception` was half of it (fixed by #579, which reads the unknown-order refusal as GONE); the other half was the command dispatcher logging `CancelOrderCommand failed: unknown_order` at ERROR because the handler let the refusal propagate. Fix: the cancel handler answers it as `CancelOrderResult.already_gone`, a value.
- **Context:** Halt of a Futures Grid → `bots` → `application/services/orders/bot_order_gateway.py` (`BotOrderGateway.cancel`), `application/kinds/grid/protection/protection_futures.py` (`_cancel_cancelling`)
- **Environment:** VPS, Futures Testnet (the exception text was not in the paste, so the incident itself is not reproduced). Reproduced on the Futures fake at `a344b25`.

## Reproduction
Not yet reproduced. Expected: a stop the exchange no longer holds is treated as done quietly. Actual (journal): `ERROR ... cancel SEW-sj9rno-42338a6e20 raised`, then `-> dropped`, then STOPPING -> STOPPED.

## Symptom
`protective stop SEW-sj9rno-42338a6e20 standing -> cancelling`, then `ERROR ... cancel SEW-sj9rno-42338a6e20 raised`, then `-> dropped`.

## Root cause
Established on the Futures fake at `a344b25` (master after #579). Two sources of ERROR for one expected outcome:
1. `bot_order_gateway.py` → `BotOrderGateway.cancel` logged `logger.exception("... cancel %s raised")` for any exception. Fixed by #579 (BUG-229): the unknown-order refusal (`-2011`) is `GONE`, logged at INFO.
2. What #579 left: `CancelOrderCommandHandler.execute` (`cancel_order/handler.py`) let `OrderRejectedByExchangeError(UNKNOWN_ORDER)` propagate, and the command dispatcher logs a handler's exception at ERROR (`App - ERROR - CancelOrderCommand failed: unknown_order: APIError(code=-2011): Unknown order sent.`). A protective stop is an algo order: `FuturesTradingClient.cancel_order` tries the regular cancel, then the algo cancel, and raises the regular refusal when neither holds the id, so a stop gone after the position closed took this path. The VPS exception text was never captured; the fake reproduces the ERROR through this path. Whether the journal's own line was this one or the gateway's (before #579) cannot be told from the paste, and both are closed.

## Fix
`CancelOrderResult` gains `already_gone` (defaulted); `CancelOrderCommandHandler` answers the unknown-order refusal as that value and still raises every other refusal; `classify_cancel` reads it as `GONE`. The desk's cancel keeps reporting such an order as not cancelled ("no longer on the exchange"). Other callers of the port see no change except that the refusal is a value.

## Regression test
- `tests/integration/modules/bots/test_cancelling_a_protective_stop_the_exchange_no_longer_holds_logs_no_error_on_the_fake_exchange.py`: the stop cancelled out of band, then the bot stopped with a close: STOPPED, flat, no record at ERROR. Red before (the dispatcher's ERROR), green after.
- `tests/unit/modules/trading/application/orders/test_cancel_order.py` (value for unknown order, other refusals still raise), `tests/unit/modules/bots/application/services/test_bot_order_gateway_close_and_cancel.py` (`already_gone` is GONE).

## Verification
The tests above, red-before/green-after on this commit, plus the commit tier. Not run on a live exchange; the real exception text of the incident is still unseen.
