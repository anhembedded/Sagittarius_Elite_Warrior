# EPIC-028P — An integration test proves Phase 1: two venues in one process, against one fake exchange, never touch each other

**Status:** 🟡 Implemented — awaiting review
**Source:** the epic-level review on PR #300 (§2, should-fix), 2026-10-01: *"'Phase 1 exit met' is claimed without the required evidence … add the dual-venue fake-exchange test, or reopen the phase."* The user agreed on 2026-10-01: *"đồng ý, làm theo đề xuất của bạn"* ("agreed, do as you propose").
**Risk:** 🟢 — a test, a request log on the fake exchange, and the one-line fix the test found
**Complexity:** S — one integration test file
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028C](../completed/EPIC-028C_both_venues_running_concurrently.md)

---

## 1. Context and problem
- Phase 1's exit row (README §4) requires an integration test against a fake exchange serving both `/fapi` and `/api` in one process. No test under `tests/integration` or `tests/sanity` does that.
- The isolation proof is unit-level only (`test_venue_isolation.py`, `Mock` clients, Emergency Stop and Enable/Disable).
- A mutation pinning order and cancel to the Futures scope was caught only by single-venue tests.

## 2. Acceptance criteria
- [x] One fake exchange serves both venues, and the test builds both venues' real adapters against it, in one process.
- [x] Each of the following, addressed to one venue, sends requests only to that venue's API family and changes only that venue's session state; the other venue's state and requests are untouched:
  - a market order;
  - a limit order and its cancel;
  - an Emergency Stop.
- [x] The test runs in both directions (Futures → Spot untouched, Spot → Futures untouched).
- [x] The README's Phase 1 exit row cites this test.

## 3. Design (as built)
- **One server, both API families.** `run_binance_fake_server()` already served `/fapi` and `/api` from one process. It now also logs every `(method, path)` it answers (`FakeServerUrls.requests`), so a test can prove what a command did *not* send.
- **Real adapters and real handlers.** Both venues' session factories, metadata providers, account readers and trading-client factories point at the one server. `ExecuteOrderCommandHandler`, `CancelOrderCommandHandler` and `EmergencyStopCommandHandler` run over one `VenueTradingScopes` serving both, as in the running app.
- **Three checks per test, in both directions.** After acting on one venue:
  - the log holds no request to the other venue's API family;
  - the other venue's resting order is still open on the exchange;
  - the other venue's session is still enabled.
- **The test found a real crossing.** Every Futures session pinged `GET /api/v3/ping`, which is the Spot API: `python-binance`'s `Client(...)` pings on construction, whatever the client is used for. A Spot testnet outage would therefore fail Futures orders, cancels and Emergency Stops before they sent anything. `FuturesSessionFactory` now builds its clients with `ping=False`; its own first call, `futures_time()`, already measures the clock skew.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/integration/application/test_two_venues_in_one_process_against_fake_server.py` | new: order, cancel, Emergency Stop, and the same symbol's two catalogs, both directions |
| `tests/sanity/fake_exchange/server.py` | the request log |
| `src/modules/trading/adapters/binance/futures_session_factory.py` | `_futures_client()`: no construction-time ping to the Spot API |

## 5. Testing
- **Red before the fix, for the right reason.** The three Futures-direction tests failed on `GET /api/v3/ping`, and nothing else crossed. The Spot direction and the catalog test passed.
- **Green after the fix:** 7 passed. The existing `tests/integration/infrastructure/binance` suite still passes.
- **Mutation:** restoring `ping=True` turns the three Futures-direction tests red again.

## Implementation notes
- `market_data`'s own `MarketDataSessionFactory` still pings on construction. It serves both markets' public klines from one client, so its ping is not a trading-venue crossing, and it is left as is.
