# BUG-199 — The sanity tier reaches the real Binance exchange, and the Market route test fails intermittently on it

- **Reported:** 2026-10-13 (master push run 38275262997 after #469, job `gate (Rest)`, `FAILED_STEPS: Sanity,Log Scan`; again on PR #471's run 38334314801, job 115090866099, whose diff touches no market data)
- **Severity:** 🟡 P2 — a red `master-warrior` that no change caused and a re-run clears; every contributor's PR can fail on it, and the tier meant to prove the app boots cleanly was talking to the live exchange from CI runners
- **Status:** ✅ Fixed (2026-10-13)
- **Board:** `test_every_navigable_route_constructs[market0]` failed intermittently because the sanity fixture redirected only `Client.API_URL` (Spot mainnet): the charts a screen opens sync Futures mainnet, both testnets and the live stream too, which went to `fapi.binance.com` / `testnet.binance.vision`, and the websocket `MagicMock` could not be awaited; fixed by one boundary (every `python-binance` endpoint, the websocket transport, a session-wide non-loopback block, and the same for the `--self-check` child process).
- **Context:** Sanity tier (`ci-rule.md` §2) → test fixtures (`tests/sanity/conftest.py`, `tests/sanity/fake_exchange/`) → Market-data venues (`src/modules/market_data/composition/market_data_venues.py`) as the consumer, unchanged
- **Environment:** GitHub Actions `ubuntu-latest`, Python 3.12, `python-binance` as locked in `requirements.lock`, engine at `engine.ref`. Reproduced locally on Linux, Python 3.12, with a connect trap that refuses and records every non-loopback destination (no packet was sent).

## Reproduction
1. From a clean checkout run `pytest tests/sanity` with a socket-level trap (the one `tests/unit/network_block.py` installs for the unit and integration tiers) active for the whole session.
2. Every `test_every_navigable_route_constructs[*]` opens a window; the window's charts sync an empty candle store for `ETHUSDT`/`1m` on `MAINNET_PUBLIC` (Spot, USD-M Futures), `SPOT_TESTNET` and `FUTURES_TESTNET`.
3. Expected: every request reaches the fake exchange. Actual: five of the six venue × market combinations reach a real host (below); only Spot mainnet reaches the fake.

Frequency in CI: intermittent, seen twice (the two runs named above). Locally deterministic once the trap is installed: every run, from the first route test to the last.

## Symptom
CI (run 38275262997, `gate (Rest)`):
```
SyncMarketDataCommand failed: APIError(code=0): Service unavailable from a restricted location ... binance.com/en/terms
  (from App.ExchangeClient "Failed to stream historical klines for ETHUSDT")
Async task 'BinanceStream[spot:BNBUSDT@1m,...]' failed: TypeError: object MagicMock can't be used in 'await' expression
```
Local, before the fix (trap installed, nothing left the machine): destinations refused `fapi.binance.com`, `testnet.binance.vision`; `ERROR App:task_manager.py:206 Async task 'BinanceStream[spot:ETHUSDT@1m]' failed: object MagicMock can't be used in 'await' expression`; and from the `--self-check` child process `api.binance.com`, `testnet.binance.vision`.

## Root cause
Three holes in one boundary, `tests/sanity/conftest.py::booted_app`:

1. **It moved one endpoint of twenty-four.** `python-binance` keeps every base URL as an attribute of `BaseClient`; the fixture set `Client.API_URL` only. A venue's client is built by `MarketDataSessionFactory` (`src/modules/market_data/adapters/binance/market_data_session_factory.py:52`) with `testnet=resolve_testnet_flag(venue)`, and the library then picks `FUTURES_URL` for a Futures read (`base_client.py` `_create_futures_api_uri`) and `API_TESTNET_URL` / `FUTURES_TESTNET_URL` for a testnet. The fixture's own comment assumed "this tier's default venue never resolves a futures-shaped call"; the Market route's charts open all four venues (`src/support/charting/live_chart/live_chart_coordinator.py:219-247`, an empty store being the one case a chart reads the exchange at rest, `BUG-172`).
2. **The websocket was a `MagicMock`, not a boundary.** `patch(".../binance_websocket_service.AsyncClient")` makes `await AsyncClient.create(...)` raise `TypeError` the moment a chart opens a stream (`binance_websocket_service.py:212`). The user-data-stream modules import their own `AsyncClient` and were not patched at all.
3. **Nothing failed on a leak.** The unit and integration tiers install `network_block` (`BUG-182`); the sanity tier did not, so a request that left the machine was only a log line.

**Why intermittent.** The syncs run on worker threads started by opening the route, and the 451/`TypeError` ERROR record is written whenever the host answers. `diagnostic_guard` fails the test running at that moment; a record that lands between tests, or after the session, is seen only by the CI log scan or not at all. So the outcome depends on the real host's latency and on which test the thread was writing in: a network race. I found no date-dependent branch on the path (the sync window is derived from now, the fake exchange answers with fixed rows, and the failure seen needs only a real host); the evidence for the mechanism is the trap trace, not a date.

**Why the gate was green.** `diagnostic_guard` observes only the test window; the integration tier's network block had no sanity counterpart. Not a case study: the blind spot (a tier without the block) is closed in this fix, and the other tiers were scanned (below).

## Fix
- `tests/sanity/fake_exchange/binance_endpoints.py` (new): `binance_clients_pointed_at(urls)` redirects **every** URL `BaseClient` declares, found by walking the class, not by a list: Spot and USD-M Futures families and the wallet family to the fake exchange, everything else to a loopback dead end. A URL a future `python-binance` adds is covered the day it is added. Both `Client` and `AsyncClient` honour it, being `BaseClient` subclasses.
- `tests/sanity/fake_exchange/stream_transport.py` (new): `AsyncClient` and `BinanceSocketManager` run unchanged; only `ReconnectingWebsocket.connect`/`recv` (inherited by every websocket class of the library, user-data streams included) are replaced.
- `tests/sanity/conftest.py`: `refused_destinations` installs `network_block` for the whole session (worker threads outlive tests) and an autouse fixture fails the test running when anything was refused, naming the host; `fake_exchange` and `stream_transport` are session fixtures; the redirect now wraps `create_gui_app`, so a client built during composition cannot keep the real host.
- `tests/sanity/fake_exchange/child_process.py` (new) and `test_self_check_process.py`: the `--self-check` subprocess gets the same three pieces through a `sitecustomize` on its `PYTHONPATH`, and the refusals it recorded are read back by the launching test.
- No change under `src/`: the application is right to open four venues; the tier's boundary was wrong.

## Regression test
`tests/sanity/test_the_booted_app_reaches_no_real_host.py` (13 tests) and `tests/sanity/test_self_check_process.py` (the five existing tests plus `test_the_real_process_reaches_no_real_host`, all through the helper's refusal check).
Red before the fix, for the stated reason: the venue × market klines reads failed with `NetworkAccessBlockedError ... 'fapi.binance.com'` / `'testnet.binance.vision'` and the autouse fixture's `the process tried to reach ["'fapi.binance.com'", "'testnet.binance.vision'"]`; the stream tests logged `Async task 'BinanceStream[...]' failed: object MagicMock can't be used in 'await' expression`; the child tests failed with `--self-check tried to reach ["'api.binance.com'", "'testnet.binance.vision'"]`. The mainnet Spot read, the one path that was redirected, was the only one that passed. Green after.

## Verification
- Red/green runs and the connect-trap trace above; whole sanity tier green locally.
- Positive proof the new boundary ran: every venue × market klines read appears in `fake_exchange.requests` (`/api/v3/klines`, `/fapi/v1/klines`); every stream opens its `ethusdt@kline_1m` URL on the fake transport.
- Other tiers scanned for the same leak: the integration tier already blocks and records every non-loopback destination (`tests/integration/conftest.py`, `BUG-182`); three integration modules still patch `AsyncClient`/`BinanceSocketManager` with plain `MagicMock`s (`test_backtest_user_flow.py`, `test_database_user_flow.py`, `test_app_integration.py`), a latent `TypeError` on a stream start that cannot reach a host there; `tests/testnet/` is the deliberate opt-in live tier. None changed here.
