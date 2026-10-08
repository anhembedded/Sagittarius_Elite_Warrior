# BUG-185 — A Bots integration test fails at teardown when a late market-data sync reaches for the network

- **Reported:** 2026-10-08 (found gating PR #429, `EPIC-035C`, by the author session; confirmed by the reviewer session)
- **Severity:** 🟡 P2 — an intermittent red `gate (Rest)` on a pull request that did not touch the code involved; costs a re-run and blurs real failures
- **Status:** Open
- **Board:** `tests/integration/modules/bots/test_bots_tab_drives_the_executor.py` errors intermittently at teardown: a background `SyncMarketDataCommand` tries to reach `testnet.binance.vision` and the no-network guard fails the test; also seen on the unchanged baseline
- **Context:** The Bots tab drives the executor ([SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)) → Module `src/modules/bots/` + `src/modules/market_data/` → `ui/` live-chart sync (`LiveChartCoordinator`) against the integration tier's network guard
- **Environment:** GitHub Actions `gate (Rest)` (Ubuntu, Python 3.12) and a Linux container, Python 3.12, engine at `engine.ref`. No credentials involved.

## Reproduction
1. On `master-warrior` at `546b8a3` (no `EPIC-035C` code), run `pytest tests/integration/modules/bots/test_bots_tab_drives_the_executor.py -q` repeatedly.
2. Expected: 6 passed every time. Actual: 1 of 3 local runs ended `6 passed, 1 error`; the same file passed 3 of 3 on the `EPIC-035C` branch. On GitHub, run 37766221009 attempt 1 failed `gate (Rest)` on this test; attempt 2 on the same sha passed.
3. Frequency: intermittent. Root cause: Not yet established.

## Symptom
```
App - ERROR - SyncMarketDataCommand failed: unit test tried to connect to 'testnet.binance.vision'; the unit tier uses no network (ci-rule.md §2) — use a loopback fake or move the test to tests/integration/
App.LiveChartCoordinator - WARNING - [live-chart] sync of BTCUSDT at 1h failed
ERROR ... test_save_and_start_saves_the_edits_on_screen_and_starts_with_them - AssertionError: the test tried to reach ["'testnet.binance.vision'"]
```
The error is reported at the test's teardown; the CI run log scan also fails on the two ERROR records.

## Root cause
Not yet established. Observed: the reach is a market-data sync started by the live chart for the selected bot's symbol, running on a worker thread that can outlive the test body, so the network guard catches it at teardown. Suspected, not verified: the same family as `BUG-182` (a late background sync caught by the integration network guard).

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Find what starts the sync (`LiveChartCoordinator`, `SyncMarketDataCommand`) in this test's graph and either give the test a loopback fake for market data or have the test wait for the sync to end before teardown (a named signal, not a sleep).
- Check `BUG-182`'s fix for the same blind spot.
