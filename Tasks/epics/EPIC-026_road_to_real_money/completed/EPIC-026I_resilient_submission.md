# EPIC-026I — Resilient submission: an explicit `recvWindow`, a timeout resolved by client order id before any resend, and backoff on rate limits

**Status:** ✅ Done (2026-10-20)
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 2; the user (2026-09-20): *"hãy cho
lô trình để có thể giao dịch thật"*.
**Risk:** 🔴 — the submit path; a naive retry sends the same order twice, which is worse than
the timeout it fixes.
**Complexity:** M — planned as one adapter method, one application policy, one new query on the port; by 2026-10-20 only the `recvWindow` was left (see the notes).
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-005` §5 ("The network fails mid-submission").
**Depends on:** None

---

## 1. Context and problem

- `-1003` and `-1015` are classified as `RATE_LIMIT`
  (`adapters/binance/binance_error_translator.py:36-39`) and then treated like any rejection: the
  coordinator logs and returns (`live_trading_coordinator.py`, the `except OrderRejectedByExchangeError`
  branch). Nothing waits; the next tick tries again immediately.
- The request timeout is 30 s (`binance_endpoints.py:31`). A submit that times out is reported as
  a failure and **not recorded as sent** (`SPEC-005` §5, deliberate) — correct for the counter,
  but the order may well be live on the exchange. Nothing queries for it.
- `recvWindow` is never set; python-binance's default applies (`exchange_status_formatter.py:14`
  reads it back for display only). `BUG-111` showed clock skew already broke every signed
  request once.
- `ClientOrderId`'s docstring describes idempotent retry as its purpose; no code does one.

## 2. Acceptance criteria

- [x] Every signed REST request carries an explicit `recvWindow` (5000 ms). *Amended 2026-10-20:
      a constant (`SIGNED_REQUEST_RECV_WINDOW_MS`), not `trading.recv_window_ms`, and no
      session-creation `CLOCK_SKEW` check against the offset: see decisions 1 and 3 below. The
      two user-data streams build their own `AsyncClient`; their WebSocket API signing adds no
      `recvWindow`, so the exchange's own 5000 ms applies there.*
- [x] `ITradingClient.get_order(symbol, client_order_id)` exists; on a timeout or a connection
      error during `place_order`, the handler queries it once before answering: found → the order
      is recorded as sent (counter, journal outcome, `known_open_symbols`); not found → answered
      as failed, never resent automatically.
- [x] `RATE_LIMIT` responses set a per-venue backoff (`Retry-After` if present, else 2 s doubling
      to 60 s) that the safety gates read as `CONNECTION_NOT_READY` until it expires; the
      coordinator's next signals are blocked with a named reason (`LiveOrderBlockedEvent`), not
      silently dropped.
- [x] No automatic resend of an order exists anywhere; a guard test asserts `place_order` is
      called at most once per `ExecuteOrderCommand` on every failure path.

## 3. Design

Timeout resolution is the standard "query before retry" idempotency pattern for exchanges that
accept a client order id; it belongs in `ExecuteOrderCommandHandler` (the one place that records
the outcome), not in the adapter (which must stay a thin ACL). Backoff state is a small
`VenueBackoff` value in `TradingSessionState` (it already holds per-session facts under the same
lock) read by `_first_blocked_safety_gate()`. `recvWindow` is a parameter of
`FuturesSessionFactory.create_trading_client()`, alongside the offset it already measures.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_trading_client.py` | `get_order()` |
| `src/modules/trading/adapters/binance/futures_trading_client.py` | `get_order()`; `recvWindow` on signed calls |
| `src/modules/trading/adapters/binance/futures_session_factory.py` | Window vs offset check |
| `src/modules/trading/application/orders/execute_order/handler.py` | Query-before-answer on timeout; backoff gate |
| `src/modules/trading/application/trading_session_state.py` | `VenueBackoff` |
| `src/config/config_keys.py`, `app_config.json` | `trading.recv_window_ms` |
| `tests/sanity/binance_fake_server.py` | Fake `GET /fapi/v1/order` and a `-1003` mode |
| `tests/unit/modules/trading/application/orders/test_execute_order_submission.py` (builders in `execute_order_builders.py`) | Timeout found / not found; backoff; at-most-once guard |
| `tests/unit/modules/trading/contracts/test_trading_client_contract.py` | `get_order()` on both implementations |
| `Docs/SPEC/SPEC-005_place_a_manual_order.md` | §5 network row split in two |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Timeout, found on exchange | unit, client faked from the interface | unit | recorded as sent, counter +1 |
| Timeout, not found | unit | unit | failed, counter unchanged, no second `place_order` |
| Rate limit | unit + fake server `-1003` mode | unit + integration | gate blocks until expiry; event published |
| Window vs offset | unit | unit | `CLOCK_SKEW` named |
| At most once | guard test | unit | green on every failure path |

See the implementation notes for what was run.

## Implementation notes

Most of this task was delivered by other work before it was closed; the 2026-10-20 review
(`REVIEW_2026-10-20_what_is_still_missing.md` §2 row 5) found `recvWindow` the only piece left.

| Criterion | Where it landed | Evidence |
| :--- | :--- | :--- |
| Explicit `recvWindow` on every signed request | This change: `SIGNED_REQUEST_RECV_WINDOW_MS` (`binance_endpoints.py`), set on the client in `new_client` | `test_binance_client_builder.py`: a real `Client` builds the query for a Futures order, cancel and account read and a Spot read; each carries `recvWindow=5000` exactly once |
| Timeout resolved by client order id, never resent | `BUG-170`: `OrderOutcomeUnknownError`, `resolve_unknown_outcome.py`, `futures_get_order(origClientOrderId=...)` | `test_execute_order_unknown_outcome.py`; `test_resilient_session.py` (a timed-out submit is sent once) |
| Backoff on rate limits | `EPIC-035D`: `RateLimitGate`, read by `connection_gate.py` as a named refusal | existing gate tests |
| No automatic resend of an order | `ResilientSession`: `ONCE` for every method not listed as a read or a cancel | `test_resilient_session.py` |

**Agent decisions** (the owner may veto; the owner pre-approved the coordinator's recommendations
on 2026-10-20):

1. **Value: 5000 ms, a constant, not a setting.** Binance recommends 5000 or less and caps it at
   60000. The library's own default is 10000 (`REQUEST_RECVWINDOW`), not the exchange's 5000 the
   task text assumed, and it overwrites a `recvWindow` passed per call, so the single seam is
   `new_client` (P5), not a parameter at call sites. The `timestamp` already carries the measured
   offset, so the window only bounds time in transit. A configured value with a cap would add a
   setting nothing has asked to change; the constant sits where `REQUEST_TIMEOUT_SECONDS` sits and
   becomes a setting when a host needs one. The `exchange-status` display used a hand-copied 5000
   and a comment that wrongly said it was the library's default; it now reads the same constant.
2. **`-1021` handling is unchanged.** `ResilientSession` already re-measures the offset and
   sends once more (`BUG-221`), for an order too: the exchange refuses the timestamp before it
   reads the order, so that resend cannot double it. A second `-1021` raises `CLOCK_SKEW`. Narrowing
   it to reads would reopen the ten-minute blind spot of `BUG-221`, whose halt could not close a
   position; the tests of that bug still pin both the single resend and the stop after two.
3. **Not done, on purpose:** the "offset larger than half the window refuses with `CLOCK_SKEW`"
   check of the first criterion. The re-measure on `-1021` and the preflight clock-skew check
   already cover the failure it guards against, and a session-open refusal would block the halt's
   close path on a skewed clock, which `BUG-221` showed to be the worse outcome.

No change to order sizing, stop or close logic.

## Resume (optional; while unfinished)
