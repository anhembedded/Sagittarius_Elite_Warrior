# BUG-180 — A network failure in a connection check writes the whole signed request URL to the run log at ERROR

- **Reported:** 2026-10-07 (found by the independent review of PR #423, round 4; filed at the coordinator's request, filing only)
- **Severity:** 🟢 P3 — the log holds a signed query string (timestamp and HMAC signature), never the API key or the secret; the signature is short-lived (Binance rejects a timestamp outside `recvWindow`). It is still request material in a log file the owner may paste into a chat or an issue.
- **Status:** ✅ Fixed (2026-10-08)
- **Board:** Fixed: `requests` words a connection error with the request's whole URL, signature included, and each caller that logged it wrote it; every trading `Client` now sends through `RedactingHttpAdapter` (mounted by `new_client`), which redacts the secrets from the failure and its whole chain once, where it is born ([EPIC-035O](epics/EPIC-035_spot_grid_unattended_safety/completed/EPIC-035O_no_signed_url_in_a_cancel_path_traceback.md)).
- **Context:** Tools → Options → Trading (Check connections), the Connect step, every account reader → `modules/trading/adapters/binance/connection_failure.py` (`classify_connection_failure`)
- **Environment:** reproduced here with a constructed `requests.exceptions.ConnectionError`; Not yet seen in the owner's own log (Binance egress is blocked in this sandbox)

## Reproduction
1. Make a signed read fail at the transport level: the network is down, a proxy refuses, or the host does not resolve. `requests` raises `ConnectionError("HTTPSConnectionPool(host='api.binance.com', port=443): Max retries exceeded with url: <url>")`, where `<url>` is the request's full URL.
2. A signed GET carries `timestamp` and `signature` in its query string, so `<url>` holds them.
3. Any caller that classifies the failure writes that text to the log:

```
>>> classify_connection_failure(ConnectionError("HTTPSConnectionPool(host='api.binance.com', port=443): Max retries exceeded with url: https://api.binance.com/sapi/v1/account/apiRestrictions?timestamp=1791380000000&signature=0123456789abcdef"), "Spot Mainnet")
ERROR App.TradingAdapter Spot Mainnet connection check failed with an unclassified exception: ConnectionError: HTTPSConnectionPool(host='api.binance.com', port=443): Max retries exceeded with url: https://api.binance.com/sapi/v1/account/apiRestrictions?timestamp=1791380000000&signature=0123456789abcdef
```

**Expected:** the log names the failure (its type and the venue) without the signed query string.
**Actual:** the whole URL, signature included.

## Symptom
The line above is the real output of the function on the constructed exception (run on master `f555f66`). Not yet reproduced from a live network failure: that needs egress to `*.binance.*`.

## Root cause
Established on `3064fe0`. `requests` raises `ConnectionError(MaxRetryError)`, and urllib3's `MaxRetryError` words itself "Max retries exceeded with url: <path>?timestamp=…&signature=…"; `str()` of the `requests` error is that text, and the traceback printed from it repeats it for the chained cause. Every logger that formatted an exception from a trading request therefore wrote the signature: `BotOrderGateway.cancel`'s `logger.exception` (`bot_order_gateway.py:186`; the cancel path of `EPIC-035O`'s audit finding M12 — `SpotTradingClient.cancel_order` catches only `BinanceAPIException`, so the transport error passes through untouched), the same call in `_submit` (`:336`), and `classify_connection_failure`'s `str(exc)` (`connection_failure.py:150-157`; this report's first form). The design fault is that the secret was removed (if at all) by whoever logged, not where the failure is born: `EPIC-035B` had done so for the user-data streams at one call site (`redact_secrets`).

Family scan: every `Client` of the trading venues is built by `new_client` (the Futures and Spot factories, the key probe, the permissions client). Not covered: the market-data session factory's own unsigned `Client` (public endpoints, no signature) and the streams' `AsyncClient`, already worded through `redact_secrets`.

## Fix
`new_client` mounts `RedactingHttpAdapter` (a `requests` `HTTPAdapter`) on every client's session. A `RequestException` raised out of `send` has its text redacted in place: arguments, `errno`/`strerror`/`filename`, `__cause__` and `__context__` (`redact_transport_failure`). The object, its class and its traceback are unchanged, so the retry policy (`classify_exchange_failure`) and every `except RequestException` behave as before; the type, host, path, `symbol` and `timestamp` stay in the text. `redact_secrets` moved from `user_stream_supervisor.py` to `transport_failure_redaction.py`: one redactor for signature, listen key and API key.

## Regression test
`tests/unit/modules/trading/adapters/binance/test_no_signed_url_in_a_transport_failure.py` — `test_a_cancel_failure_logs_no_signature` scans the gateway's captured log and outcome detail; `test_every_signed_call_of_the_client_fails_without_the_query` scans `str`, `repr`, the traceback and the chain for cancel, cancel-all, order send, open orders and account; `test_a_connection_check_logs_no_signature` is this report's first form. They use the real python-binance `Client` built by `new_client` over a fake transport at `HTTPAdapter.send`, no `Mock` standing in for the crash. Red before the fix (8 failed with the signature in the log), green after. `test_binance_client_builder.py::test_every_session_sends_through_the_redacting_adapter` locks the mount for all four venues, signed and unsigned.

## Verification
Positive proof the new mechanism ran: the captured log of the cancel test holds `…/api/v3/order?timestamp=…&signature=<redacted>` in the gateway's `logger.exception` traceback (seen by running the path, not inferred), and the connection-check line holds the same. Commit tier PASS; `tests/unit/modules/trading`, `tests/unit/modules/bots` and `tests/unit/architecture` green. Not run: a live network failure (no egress to `*.binance.*` here), and the `-Full` gate, which GitHub runs on the PR.
