# EPIC-027J — The fake exchange answers the Spot API, so every Spot path is tested at the network boundary

**Status:** ✅ Done (2026-09-27)
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
- [x] Spot routes:
  - signed `POST /api/v3/order` and `/api/v3/order/test`
  - `GET /api/v3/openOrders`
  - `DELETE /api/v3/order` and `/api/v3/openOrders`
  - `GET /api/v3/account` with balances
  - `GET /api/v3/time`
  - `/api/v3/userDataStream` (`POST`/`PUT`/`DELETE`)
  - an `exchangeInfo` that carries real-shaped filters
  (`spot_routes.py`; `test_fake_exchange_spot_routes.py`)
- [x] A filled Spot order moves balances (quote → base on BUY, base → quote on SELL, fee in the
      received asset), and a user-data event is emitted in Binance's `executionReport` /
      `outboundAccountPosition` shape. (`spot_account_state.py::SpotAccountState._fill_market_order`,
      `_emit_fill_events`; `test_a_filled_market_buy_moves_quote_to_base_minus_fee_in_base`,
      `test_a_filled_market_sell_moves_base_to_quote_minus_fee_in_quote`,
      `test_a_fill_queues_execution_report_and_account_position_events`)
- [x] Payload shapes are taken from Binance's documented responses and pinned by fixtures. The fixture
      source is cited in the file. (`spot_routes.py`'s own module docstring cites `python-binance`'s
      `client.py`; `spot_account_state.py`'s docstring cites `create_order()`'s own `FULL` response
      docstring and Binance's Spot User Data Streams documentation)

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
- The fake's own contract tests: every route against a documented example payload, exercised through
  a real, unpatched-except-for-URL `binance.client.Client` — the established precedent
  (`test_session_factories_against_fake_server.py`) for testing a fake network boundary without
  writing a hand-written port double (`testing-rule.md`), since `EPIC-027K`'s real Spot
  `ITradingClient` adapter does not exist yet to drive these routes through.
- New file `tests/integration/infrastructure/binance/test_fake_exchange_spot_routes.py` (9 tests):
  exchangeInfo filter shape, a test-order touches no balance, a filled MARKET BUY/SELL moves balances
  correctly (fee in the received asset), a fill queues both user-data event shapes, a LIMIT order
  stays open until canceled, canceling an unknown order gets Binance's real `-2011` shape, cancel-all
  answers a list of canceled orders, and the listen-key lifecycle round-trips.
- Ran: `.venv/bin/ruff check`/`format --check` (clean), `pytest tests/unit/architecture -q`
  (451 passed), `pytest tests/integration/infrastructure/binance tests/sanity -q` (51 passed,
  includes the 9 new tests and every pre-existing Futures-side fixture test, confirming the
  `server.py` dispatch refactor did not regress Futures routing).

## Implementation notes (written when done)
- `server.py`'s four near-identical `do_GET`/`do_POST`/`do_PUT`/`do_DELETE` bodies were collapsed into
  one shared `_dispatch(method, path, params)` that routes by path prefix (`/api/` → Spot, `/fapi/` →
  Futures) — before this, only `do_GET` ever consulted `spot_routes` at all; `do_POST`/`PUT`/`DELETE`
  called `handle_futures` unconditionally, which is exactly the gap this task's own "wire the Spot user
  data stream" file-table entry was naming. `_Handler` now holds two independent state attributes
  (`order_book: OrderBookState`, `spot_account: SpotAccountState`), never a union of the two.
- `exchangeInfo`'s filter shape was verified against the *real* parser this application already runs
  (`market_metadata_parser.py`), not guessed or copied from the Futures fake: it expects
  `baseAsset`/`quoteAsset` at the symbol level and the current Binance filter name
  `NOTIONAL`/`minNotional` (the parser also accepts the legacy `MIN_NOTIONAL`/`notional` as a fallback,
  but the fixture uses the shape Binance's own `get_symbol_info()` docstring and this parser's own
  example both show as current).
- Fee rate (0.1%, in the asset received) and reference prices (BTCUSDT 50000, ETHUSDT 3000) are the
  fixture's own fixed constants — `SpotAccountState` is deliberately not a matching engine (no order
  book, no partial fills, no slippage), matching `OrderBookState`'s own explicit "no matching engine"
  scope on the Futures side. `EPIC-027K` is unaffected by this: it drives the same routes through a
  real adapter, not through this fixture's fill arithmetic.
