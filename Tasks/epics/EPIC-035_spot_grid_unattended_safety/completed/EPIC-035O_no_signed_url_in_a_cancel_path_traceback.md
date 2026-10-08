# EPIC-035O — No signed URL in a cancel-path traceback

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M12 / BUG-180 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟡 — a signed URL in a log is a credential-adjacent leak
**Complexity:** S
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit M12 and [`BUG-180`](../../../bug_report/completed/BUG-180_a_network_failure_in_a_connection_check_logs_the_signed_request_url_at_error.md): on the cancel path a `requests` error reaches `logger.exception`, so the traceback carries the signed URL (the audit marks it inferred). Cited: `src/modules/trading/adapters/binance/spot/spot_trading_client.py:139`, `src/modules/bots/application/services/bot_order_gateway.py:156`, `src/modules/trading/adapters/binance/connection_failure.py:150-155`. Fix at the mechanism: one transport-error sanitiser used by every path (`fix-bug-rule.md` §1), and close `BUG-180` through `create-bug-report-rule.md`.

**Re-verified on `3064fe0` (master-warrior), 2026-10-08.** The mechanism holds; the citations moved.
- `spot_trading_client.py` `cancel_order` (`:139` then) catches only `BinanceAPIException`; a `requests` error is not one, so it leaves the client untouched. ✅ holds.
- `bot_order_gateway.py` `BotOrderGateway.cancel` now logs through `logger.exception` at `:186` (`:156` is stale: the file grew); `_submit` has the same call at `:336`. ✅ holds.
- `connection_failure.py` `classify_connection_failure` logs `exc` at `:150-157`. ✅ holds.
- **"Inferred" is now observed.** The real python-binance `Client`, built by `new_client` over a fake transport under `requests`' adapter, wrote `…/api/v3/order?timestamp=…&signature=<value>` into the captured log and into `str`, `repr` and the traceback of the exception and of its chained cause. Red before (8 failed).
- **A redactor already existed, for the streams only.** `EPIC-035B` put `redact_secrets` in `user_stream_supervisor.py` (signature, listen key, API key) and applied it at one call site. Building a second would have been two mechanisms for one secret, so it moved to `transport_failure_redaction.py` and the supervisor imports it.
- Not seen from a live network failure: this sandbox has no egress to `*.binance.*`.

## 2. Acceptance criteria
- [x] A network failure on the cancel path logs no signed URL, signature or API key anywhere in the message, the traceback or the chained exception. Evidence: `test_a_cancel_failure_logs_no_signature` (gateway → real `SpotTradingClient`-shaped cancel → real `Client`; scans `caplog.text` and the outcome's detail), `test_every_signed_call_of_the_client_fails_without_the_query` (cancel, cancel-all, order send, open orders, account; scans `str`, `repr`, traceback and chain), `test_a_listen_key_and_an_api_key_in_a_failure_are_removed_with_the_signature`. All red before, green after.
- [x] The order-send and connection-check paths use the same sanitiser (one mechanism). Evidence: the order-send and account calls are parametrised in the test above; `test_a_connection_check_logs_no_signature` covers `classify_connection_failure`; `test_every_session_sends_through_the_redacting_adapter` locks that `new_client` mounts it for all four venues, signed and unsigned.
- [x] `BUG-180` is updated per the bug rule and its board line written: moved to `completed/`, Fixed 2026-10-08.

## 3. Design
A single sanitiser at the transport boundary that rewrites the exception before anything logs it.

Chosen: the lowest seam every python-binance request crosses, `requests`' own adapter. `new_client` is the one function that builds a trading `Client` (and the key probe and permissions client use it too), so it mounts `RedactingHttpAdapter` on the client's session; a `RequestException` raised out of `send` has its secrets redacted in place (arguments, `errno`/`strerror`/`filename`, cause and context) and is re-raised as the same object. Rejected: redacting at `BotOrderGateway.cancel` and `classify_connection_failure` (the call sites reported; the next logger would leak again), and `ResilientSession` (it does not cover the key probe and permissions clients, which open `new_client` directly).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/transport_failure_redaction.py` | New: `redact_secrets` (moved from the stream supervisor) and `redact_transport_failure` |
| `src/modules/trading/adapters/binance/redacting_http_adapter.py` | New: the adapter that applies it |
| `src/modules/trading/adapters/binance/binance_client_builder.py` | Mounts the adapter on every client's session |
| `src/modules/trading/adapters/binance/user_stream_supervisor.py` | Imports `redact_secrets` instead of defining it |

## 5. Testing
Unit tier, `tests/unit/modules/trading/adapters/binance/test_no_signed_url_in_a_transport_failure.py` and `test_binance_client_builder.py`; the real `Client` over a fake transport at `requests.adapters.HTTPAdapter.send`. Red before: 8 of the file's tests failed with the signature in the log (the control that a failure without a query is left alone passed). Green after: the whole `tests/unit/modules/trading` tree. Mutation: replacing the redaction with a no-op turned 7 tests red.

## Implementation notes
- **Not covered, deliberately:** the market-data session factory builds its own unsigned `Client` for public endpoints (no `signature` in its URLs), and the user-data streams use python-binance's `AsyncClient` over aiohttp, whose failures are already worded through `redact_secrets` (`EPIC-035B`). Neither is a trading `Client`.
- What a log keeps: the exception's type, the host, the path, and the unsecret query values (`symbol`, `timestamp`). The secret values read `<redacted>`.
- `RequestException.request` (and `.response`) keep their objects, with the URL and a signed form body redacted and the `X-MBX-APIKEY` header replaced (review of PR 447, finding 2): `test_the_request_a_failure_carries_holds_no_signature_or_key`.
- **urllib3's own DEBUG log** writes request paths with their query on the `urllib3` logger. The engine configures only the `App` logger (`StdLogger`, `propagate = False`), so `--dev` and `--debug` do not write urllib3's lines to the run log; established by reading `std_logger.py`, not by a run. A root logger set to DEBUG by hand would.
- The construction-time ping runs inside `Client.__init__`, before the adapter is mounted; it is unsigned and carries no query.

## Resume
Done. Nothing owed.
