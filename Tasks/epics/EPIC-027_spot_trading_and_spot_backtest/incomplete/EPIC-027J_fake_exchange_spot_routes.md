# EPIC-027J — The fake exchange answers the Spot API, so every Spot path is tested at the network boundary

**Status:** 🔵 Backlog
**Source:** found while measuring the Spot gap, 2026-09-26. It is required by the test contract (`testing-rule.md`, `EPIC-009` ADR).
**Risk:** 🟡 — a fake that answers what the code asks, instead of what Binance answers, would hide real bugs (`BUG-026`, `CS-001`).
**Complexity:** M — signed routes, balance-mutating state, a user data stream.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** None. It can run in parallel with `EPIC-027F`/`G`.

---

## 1. Context and problem
- The fake exchange serves Futures in full (`tests/sanity/fake_exchange/futures_routes.py:6-25,115-192`).
- For Spot it serves only three unsigned GETs: ping, a minimal `exchangeInfo` **without filters**,
  and empty klines (`spot_routes.py:21-30`).
- Order state is Futures-shaped, including `reduceOnly` (`order_book_state.py:27-45`).
- The substitution rule is fixed: replace only at the network boundary, at configuration — never a
  hand-written port double (`testing-rule.md`; `EPIC-009` ADR).

## 2. Acceptance criteria
- [ ] Spot routes:
  - signed `POST /api/v3/order` and `/api/v3/order/test`
  - `GET /api/v3/openOrders`
  - `DELETE /api/v3/order` and `/api/v3/openOrders`
  - `GET /api/v3/account` with balances
  - `GET /api/v3/time`
  - `/api/v3/userDataStream`
  - an `exchangeInfo` that carries real-shaped filters
- [ ] A filled Spot order moves balances (quote → base on BUY, base → quote on SELL, fee in the
      received asset), and a user-data event is emitted in Binance's `executionReport` /
      `outboundAccountPosition` shape.
- [ ] Payload shapes are taken from Binance's documented responses and pinned by fixtures. The fixture
      source is cited in the file.

## 3. Design
- A second state object beside the Futures one, not a union of both. Spot and Futures accounts are
  different facts.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/sanity/fake_exchange/spot_routes.py` | the routes above |
| `tests/sanity/fake_exchange/spot_account_state.py` | balances and orders |
| `tests/sanity/fake_exchange/server.py` | wire the Spot user data stream |

## 5. Testing
- The fake's own contract tests: every route against a documented example payload.
- Not run yet.
