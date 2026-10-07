# BUG-170 — An HTML answer from the exchange to an order submit is reported as "order rejected", while the order may be live

- **Reported:** 2026-10-07 (the reviewer of PR #414, a PR comment: https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/414#issuecomment-6032728065)
- **Severity:** 🔴 P1 — with real money the app believes an order is not placed while it may be live on the exchange, so a bot or the user can place it a second time or leave a position unwatched
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** A non-JSON answer (a gateway's `502 Bad Gateway` page) or a transport failure while placing an order is raised as `OrderRejectedByExchangeError`, so the app reports the order as rejected; whether it reached the exchange is unknown.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `src/modules/trading/` → `adapters/binance/` (the two trading clients), `application/orders/execute_order/` (the handler); consumers in `src/modules/bots/` and `src/modules/strategy/`
- **Environment:** `master-warrior` at `edad1e5` (after PR #414); Linux; Spot and Futures Testnet. Not seen on a live account.

## Reproduction
1. Have the exchange answer an order submit with an HTML page (`502 Bad Gateway`) after it accepted the order (a gateway that fails on the way back), or drop the connection after the request left.
2. Place an order live, by hand or through a bot.
3. Expected: the app says the outcome is unknown, asks the exchange for the order by its client order id, and reports placed, not placed, or still unknown with the reason.
4. Actual: `OrderRejectedByExchangeError` with reason `UNKNOWN` ("the exchange is unavailable (HTTP 502 Bad Gateway)"); the strategy logs "Live order rejected", the CLI prints "Exchange rejected the order", a bot treats the order as not placed. Not reproduced against a real exchange; reproduced with the real clients over a session double that raises python-binance's own exception (see the regression tests).

## Symptom
The reviewer's finding on PR #414: `_raise_rejection` (`futures_trading_client.py:257`, `spot_trading_client.py:160`) wraps every `BinanceAPIException` as a rejection, including python-binance's `code=0` exception for a body that is not JSON. A rejection means the exchange read the request and refused it. An HTML page means nobody can say. A `BinanceRequestException` or a `requests` timeout while sending is the same case, and was left to propagate as a raw exception, which the callers log as a network error or turn into a fault with the exception's text.

## Root cause
`place_order` in both clients had one `except BinanceAPIException` that ended in `_raise_rejection` (`futures_trading_client.py:257`, `spot_trading_client.py:160` before the fix): no branch for an answer that is not an API reply (python-binance's `code=0` exception for a page), and a `BinanceRequestException` or `requests` timeout propagated raw. A rejection means the exchange read the request and refused it; both cases say nothing about that. `ITradingClient` had no read by client order id, although the id exists before the send (`contracts/client_order_id.py`), so nobody could settle the doubt. The gate was green because every existing test fed a JSON rejection or a transport error that no caller distinguished.

## Fix
- `contracts/order_outcome_unknown.py`: `OrderOutcomeUnknownError` (may be live) and `OrderNotPlacedError` (the exchange holds no such order).
- `adapters/binance/order_send_failure.py`: the one decision for a failed send or read. A live send (any mode but `VALIDATE_ONLY`, which never creates an order) that got a page or a transport failure raises the unknown outcome with a plain reason; an answer the exchange gave stays a rejection. `ITradingClient.find_order` (both clients) reads by `origClientOrderId`, and a Futures stop-limit by `clientAlgoId`; `-2013` is "no such order".
- `ExecuteOrderCommandHandler._resolve_unknown_outcome` reads the order back: found continues as a placed order, `None` raises `OrderNotPlacedError`, an unreadable read raises `OrderOutcomeUnknownError` after counting the order as sent (limits and the symbol's open slot hold).
- The same decision covers Binance's coded "execution status unknown" answers (`-1006`, `-1007`): they carry a code but are no refusal (review of PR #416). `resolve_unknown` (`application/orders/resolve_unknown_outcome.py`) is shared by the execute handler and the emergency stop, whose closes and surplus sales used to call `place_order` unresolved: an unconfirmed close is said to be possibly done and the next position still closes; an unconfirmed sale is not sent again.
- Consumers: `BotOrderGateway` turns both into a fault, carrying the unknown order's id so the stop sequence marks it off the ladder; `LiveTradingCoordinator` logs the unknown at ERROR ("may be live") and not-placed at WARNING, neither as a rejection; `trade-once` words them separately. The manual order panel, TP/SL follower and close button show the exception's own text, which now says "outcome unknown, it may be live"; their move to a message box is `BOT-169`.

## Regression test
- `tests/unit/modules/trading/adapters/binance/test_order_outcome_unknown.py` (both venues): a page, a read timeout and a `BinanceRequestException` on a live send raised `OrderRejectedByExchangeError` or the raw error before the fix, `OrderOutcomeUnknownError` now; `find_order` cases.
- `tests/unit/modules/trading/application/orders/test_execute_order_unknown_outcome.py`: placed, not placed, still unknown (counted as sent), the read carries the submitted id. Red before the fix with the page surfacing as a rejection.
- `test_live_trading_coordinator_unknown_outcome.py`, `test_bot_order_gateway_unknown_outcome.py`, one case in `test_grid_executor_start.py`. The real clients run over a `Mock` session; no double stands in for the crashing method.

## Verification
Commit tier green (`ci-local.ps1 -SkipTests`, `LOG_FILE` scanned: no FAILED/ERROR/Traceback); `tests/unit` 8,536 passed locally (the checkout-name guard excluded: it needs the repository folder name of a CI checkout); mypy clean; the live-mode and ruff-debt guards pass (the `trade_once_cmd.py` T20 baseline lowered 12 → 11). Positive proof the mechanism ran: the handler tests assert the `[order-outcome-unknown]`, `[order-not-placed]` and `[order-confirmed]` paths by their outcome. Not run against a real exchange. The `-Full` run is GitHub Actions'.
