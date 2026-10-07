# BUG-180 — A network failure in a connection check writes the whole signed request URL to the run log at ERROR

- **Reported:** 2026-10-07 (found by the independent review of PR #423, round 4; filed at the coordinator's request, filing only)
- **Severity:** 🟢 P3 — the log holds a signed query string (timestamp and HMAC signature), never the API key or the secret; the signature is short-lived (Binance rejects a timestamp outside `recvWindow`). It is still request material in a log file the owner may paste into a chat or an issue.
- **Status:** Open
- **Board:** `classify_connection_failure` logs `str(exc)` at ERROR for every failure that is not a Binance code it knows; for a `requests` connection error that text is the whole URL, `?timestamp=…&signature=…` included.
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
Not yet established as to design intent; the mechanism is read from the code, not proven by a live run.
- `connection_failure.py` (`classify_connection_failure`, the `logger.error(... "%s: %s", type(exc).__name__, exc)` call) formats the exception with `%s` so that the catch-all bucket "leaves the real exception in the run log" (`BUG-137`, `code/errors.md` #1). That rule is right; the text of a transport exception is what puts the URL in.
- The same function is called by both account readers, the key gate and the key probe, so the exposure is shared; `describe_failure` (the wording function beside it) returns `str(exc)` for any non-key, non-HTML failure too, so a screen that shows that wording has the same text (the Options page does not: `BUG-176` keeps a transport failure's text out of the verdict's reason).
- Which other callers log or show `str(exc)` of a `requests` error is Not yet established: a family scan has not been run (filing only).

## Fix
Not yet written (filing only).

## Regression test
Not yet written. A test would pass a `ConnectionError` holding a signed URL to `classify_connection_failure` and assert the ERROR record's text holds no `signature=`; red on master.

## Verification
Not run.

## Suggested next steps
- Decide the wording: the exception's type and the host, or the message with the query string removed; either keeps `BUG-137`'s promise that the real failure is in the log.
- Fix it once in `connection_failure.py` (the one place both readers, the gate and the probe classify through), then scan for the same `%s`-of-a-`requests`-error pattern in the other adapters (order send, history reads, the user data stream) and fix the family at the same mechanism (`fix-bug-rule.md` §2).
