# BUG-226 — Cancelling a protective stop that is already gone after the position closed logs `ERROR ... cancel ... raised`

- **Reported:** 2026-10-19 (coordinator session, from the owner's VPS journal of the BUG-225 incident, bot `sj9rno`)
- **Severity:** 🟢 P3. The bot still ended STOPPED and flat; only the log level misleads.
- **Status:** Open
- **Board:** After a halt closed the position, cancelling the bot's protective stop logged an ERROR (`cancel SEW-sj9rno-42338a6e20 raised`) though the stop was dropped correctly right after.
- **Context:** Halt of a Futures Grid → `bots` → `application/services/orders/bot_order_gateway.py` (`BotOrderGateway.cancel`), `application/kinds/grid/protection/protection_futures.py` (`_cancel_cancelling`)
- **Environment:** VPS, Futures Testnet. The exception text was not in the paste. Not reproduced.

## Reproduction
Not yet reproduced. Expected: a stop the exchange no longer holds is treated as done quietly. Actual (journal): `ERROR ... cancel SEW-sj9rno-42338a6e20 raised`, then `-> dropped`, then STOPPING -> STOPPED.

## Symptom
`protective stop SEW-sj9rno-42338a6e20 standing -> cancelling`, then `ERROR ... cancel SEW-sj9rno-42338a6e20 raised`, then `-> dropped`.

## Root cause
Not yet established. Suspected from reading the code at `6c70156` (not run): `BotOrderGateway.cancel` logs any exception from the cancel with `logger.exception` (`bot_order_gateway.py`, "cancel %s raised"), and a closePosition stop may be gone from the exchange once the position is flat; `ProtectionFutures._cancel_cancelling` then resolves it through the open-stops check (`UNKNOWN_ORDER`), which is why it ends `dropped`. If so the outcome is right and the severity of the log line is wrong. The exception text is needed to confirm.

## Suggested next steps
Read the exception text in the VPS journal; if it is Binance's unknown-order error, log it below ERROR for a protective-stop cancel. Out of scope of BUG-225.
