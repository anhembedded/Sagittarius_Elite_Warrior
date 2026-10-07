# BUG-182 — Booting the Trade mode in a UI integration test asks the real binance.com for the Watchlist's filters

- **Reported:** 2026-10-07 (gating PR #426: CI logged `WARNING App.Trading.Market … could not read spot filters … 451`; the same on master)
- **Severity:** 🟡 P2 — a test suite that depends on a live exchange passes or fails by the runner's region, and a worker that swallowed the refusal hid it
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** Every UI integration test that showed the Trade mode went to binance.com for the Watchlist's exchange filters (a 451 warning in CI). Cause: `app_engine` substituted four market-data ports but not `ISymbolMetadataProvider`, and no network block covered the integration tier, whose worker also swallows the error. Fix: the verified fake is bound in `app_engine`, and the integration tier now refuses and records every non-loopback connection, failing the test that made one.
- **Context:** [SPEC-002](../../Docs/SPEC/SPEC-002_watch_the_live_market.md) (the Watchlist) → Trading (`src/modules/trading/ui/market/`) → test composition (`tests/integration/`)
- **Environment:** CI (`gate (Rest)`, no proxy) and a Linux container; engine `f4ef582`. No real exchange was called here: the container's own network is behind a loopback proxy and the block refused the request before any packet left.

## Reproduction
1. `pytest tests/integration/presentation/ui -k "market or conformance or screenshots"` with the network block of the unit tier applied.
2. Expected: no test reaches a host. Actual: 15 tests (`test_main_window_state`, `test_market_mode_default_indicators`, `test_menu_groups`, `test_workbench_conformance`, `test_workbench_screenshots`) went to `api.binance.com` from the Watchlist's filters worker. Every run, whichever the runner's region.

## Symptom
```
App.Trading.Market - WARNING - [market] could not read spot filters: APIError(code=0): Service unavailable from a restricted location according to 'b. Eligibility' in https://www.binance.com/en/terms.
```
With the block applied: `… could not read spot filters: unit test tried to connect to 'api.binance.com'` — logged, and the test still green.

## Root cause
`WatchlistFilters.fetch` (`src/modules/trading/ui/market/watchlist_filters.py`) runs `ISymbolMetadataProvider.get_or_fetch` on a worker when the Watchlist goes live. `tests/integration/presentation/ui/conftest.py::app_engine` bound `IHistoricalKlines`, `IMarketStream`, `IRangeCoverage` and `ISymbolCatalog` but not this port, so the container's real `BinanceSymbolMetadataProvider` answered. Three nets were silent: the unit tier's network block (`tests/unit/conftest.py`) does not cover `tests/integration/`; the worker's `except Exception` turns any refusal into a `WARNING`; and in a sandbox with a loopback forward proxy the block's loopback exemption lets the request through to the proxy. The gate's log scan reads `WARNING` records, which is how it showed at all.

## Fix
- `tests/integration/presentation/ui/conftest.py`: the `symbol_metadata` fixture (`FakeSymbolMetadataProvider`) is bound to `ISymbolMetadataProvider` next to the other four ports.
- `tests/unit/network_block.py`: `install(monkeypatch)` is the one definition of the block (moved out of `tests/unit/conftest.py`); it records every refused destination, and removes the proxy variables so a loopback proxy cannot carry a request out.
- `tests/integration/conftest.py`: the integration tier applies it and fails a test whose run was refused, wherever the error was caught. Loopback fake servers stay allowed.

## Regression test
`tests/integration/conftest.py::_block_non_loopback_connections` (autouse): with the fake unbound it errored 15 tests at teardown with `the test tried to reach ['api.binance.com']`; with the fake bound they pass. `tests/unit/test_unit_tests_never_reach_the_network.py::test_a_refusal_is_recorded_even_when_the_caller_swallows_it` and `::test_a_loopback_proxy_in_the_environment_cannot_carry_a_request_out` pin the two new halves of the block.

## Verification
`pytest tests/integration -n 4` with proxy variables unset: 437 passed, 1 failed (`BUG-183`, a different defect). Unit network tests 25 passed. Commit tier (`ci-local.ps1 -SkipTests`) PASS. Positive proof the fake ran: the Watchlist's worker now logs `[market] spot filters read (… listed: False)` where it logged the warning. Not run: the sanity tier under the block — it boots the real composition root and may hold the same blind spot.
