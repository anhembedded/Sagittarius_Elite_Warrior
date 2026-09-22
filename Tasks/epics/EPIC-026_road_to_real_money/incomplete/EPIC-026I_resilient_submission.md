# EPIC-026I — Resilient submission: an explicit `recvWindow`, a timeout resolved by client order id before any resend, and backoff on rate limits

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 2; the user (2026-09-20): *"hãy cho
lô trình để có thể giao dịch thật"*.
**Risk:** 🔴 — the submit path; a naive retry sends the same order twice, which is worse than
the timeout it fixes.
**Complexity:** M — one adapter method, one application policy, one new query on the port.
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

- [ ] Every signed request carries an explicit `recvWindow` from config
      (`trading.recv_window_ms`, default 5000), validated against the measured clock offset at
      session creation: an offset larger than half the window refuses with `CLOCK_SKEW` before
      any order.
- [ ] `ITradingClient.get_order(symbol, client_order_id)` exists; on a timeout or a connection
      error during `place_order`, the handler queries it once before answering: found → the order
      is recorded as sent (counter, journal outcome, `known_open_symbols`); not found → answered
      as failed, never resent automatically.
- [ ] `RATE_LIMIT` responses set a per-venue backoff (`Retry-After` if present, else 2 s doubling
      to 60 s) that the safety gates read as `CONNECTION_NOT_READY` until it expires; the
      coordinator's next signals are blocked with a named reason (`LiveOrderBlockedEvent`), not
      silently dropped.
- [ ] No automatic resend of an order exists anywhere; a guard test asserts `place_order` is
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
| `tests/unit/modules/trading/application/orders/test_execute_order.py` | Timeout found / not found; backoff; at-most-once guard |
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

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
