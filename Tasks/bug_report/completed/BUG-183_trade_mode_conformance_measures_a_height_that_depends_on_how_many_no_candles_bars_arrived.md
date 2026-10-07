# BUG-183 — `test_workbench_conformance[1024x700]` measures a Trade height that depends on how many "no candles" bars have arrived

- **Reported:** 2026-10-07 (gating PR #426: `gate (Rest)` on a2dcedb failed once with `trade@1024x700/fits_the_window: needs 643x701`, a re-run passed)
- **Severity:** 🟡 P2 — a green or red gate that depends on worker timing; each flake costs a gate cycle and teaches the reviewers to re-run
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** The Trade mode needed 701 px in a 700 px window on one CI run only. Cause: the test boot left the per-venue market-data ports (`IMarketDataSources`) real, so each of the four desks' chart workers read an empty store and raised a 43 px "no candles" message bar, a different number of them by the time the layout was measured; fonts only scaled each bar. Fix: the boot binds a fake `IMarketDataSources` serving the seeded candles for every venue and market, so no bar arises.
- **Context:** [SPEC-002](../../Docs/SPEC/SPEC-002_watch_the_live_market.md) → Trading (`src/modules/trading/ui/desk/`, `src/support/charting/live_chart/`) → test composition (`tests/integration/presentation/ui/`)
- **Environment:** CI (`gate (Rest)`) and a Linux container with the Inter font as the system sans (Trade 715 px, Backtest 706 px, the owner's numbers too); engine `f4ef582`.

## Reproduction
1. `pytest tests/integration/presentation/ui/test_workbench_conformance.py` locally: `trade@1024x700/fits_the_window: needs 623x715 (the mode 583x543, the window around it 40x172)`, every run.
2. Count the bars while Trade shows: `MessageBarHost.bar_count()` was 4 (one run measured 3 labels).
3. In CI the same window needed 701: the same four bars with a smaller font, and passed on the re-run, when fewer had arrived.

## Symptom
`trade@1024x700/fits_the_window: needs 643x701 (the mode 603x532, the window around it 40x169)`, one pixel over. The mode's 543 px locally broke down as: mode header 30, `MessageBarHost` **190** (4 bars × 43 plus spacing), `TradeView` 323. At rest, with no bar, the mode needs about 355 px.

## Root cause
`MarketDataCandleFeed` (`src/modules/market_data/contracts/market_data_candle_feed.py`) reads `IMarketDataSources.ports_for(venue)` per desk. `tests/integration/presentation/ui/conftest.py::app_engine` substituted the default-venue singletons (`IHistoricalKlines`, `IMarketStream`, …) but not `IMarketDataSources`, so every desk read the real, empty per-venue store, and the dispatcher stub made its sync succeed with nothing stored. `LiveChartCoordinator._fetch_what_is_missing` (`live_chart_coordinator.py:224-231`) then raised `load_failed("The exchange has no 1m candles of ETHUSDT …")` from its worker, which opens one bar per desk cause in the mode's `MessageBarHost` (their detail is empty, so `_bar_showing_text` never merges them). `fit_problems` measures `minimumSizeHint` after three `processEvents()` passes, before or after each worker reported: 0 to 4 bars, 0 to 190 px. The fixture also seeded the Spot market only, so a Futures desk would have found nothing even through the fake.

The font dependence the report suspected is real but secondary: it scales each bar's and control's height (701 vs 715 for the same four bars). With no bar the mode is far under 700 on any font, so the test no longer lives on a one-pixel margin.

The gate was green while the measurement was racy because the check reads a state ("at rest") the boot did not make true; no other net asserts what the boot holds.

## Fix
- `tests/integration/conftest.py`: `market_data_sources` fixture, a `FakeMarketDataSources` serving every `MarketDataVenue` from the seeded history, stream and coverage; `seeded_history` (moved here with `market_stream`) seeds Spot and Futures USD-M.
- `tests/integration/presentation/ui/conftest.py`: `app_engine` binds it to `IMarketDataSources`.

## Regression test
`tests/integration/presentation/ui/test_every_desk_reads_a_seeded_store.py` (6 cases, venue × market): with the binding removed all six failed with `<venue> / <market> reads an empty store`; with it they pass. It asserts the precondition of every bar rather than racing the workers. The conformance check itself is unchanged: threshold and sizes are as before.

## Verification
`pytest tests/integration -n 4`: 443 passed; `test_workbench_conformance` six runs in a row with Trade not reported (the window's minimum height is now set by Backtest alone). Positive proof: the probe's bar count is `[0, 0, 0, 0, 0, 0]` where it was `[0, 0, 0, 0, 4, 0]`, and the seeded store logs reads of `ETHUSDT` for Spot and Futures USD-M. Commit tier PASS.

**Still open, not this defect:** locally the same test fails on Backtest at 1024x700 (`needs 719x706`, the Run setup dock's 322 px) with the Inter font; CI's font passes it with an unknown margin. Reducing it is a Backtest layout change; filed for the owner's decision, not changed here. Separately, four desks' identical "no candles" notices do not merge (empty detail), so a real user on an empty store sees up to four bars.
