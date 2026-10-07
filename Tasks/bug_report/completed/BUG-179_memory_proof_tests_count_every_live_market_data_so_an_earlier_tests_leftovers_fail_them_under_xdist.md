# BUG-179 — The BUG-025 memory proofs fail with the xdist worker's ordering: `assert -30 == 0`

- **Reported:** 2026-10-07 (PR #422's `gate (Unit)`, twice on head `a30706f5`; the coordinator saw it fail on merged master too)
- **Severity:** 🟡 P2 — a green change goes red on a test it does not touch, and a negative offset could hide a real leak.
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** The BUG-025 stream memory proofs compared every live `MarketData` with the count at their start, so objects an earlier test on the same xdist worker released mid-run gave `-30`. Fixed: a shared `MarketDataWatch` counts only objects created during the stream, in both proofs.
- **Context:** Test tier → `tests/unit/modules/market_data/adapters/binance/test_python_binance_client_unit.py`, `tests/integration/modules/market_data/adapters/persistence/test_sqlalchemy_repository.py`, shared `tests/market_data_watch.py`
- **Environment:** GitHub Actions, Python 3.12, `-n` workers; not reproduced locally.

## Reproduction
Not reproduced locally (the exact CI command `ci-local.ps1 -Full -Part Unit`, and plain `-n 2/3/4`, pass). In CI the failure repeated identically on a re-run, so it follows which tests share a worker, which PR #422's added tests shifted.

## Symptom
`FAILED …/test_python_binance_client_unit.py::test_streaming_and_discarding_chunks_never_lets_more_than_one_chunk_stay_alive - assert -30 == 0`

## Root cause
`_live_market_data_count()` counted every `MarketData` on the GC heap and the test asserted `count_after − count_before == 0`. Thirty objects alive at the start (kept by something an earlier test on the worker left behind) were released while the stream ran, so the difference was −30. The test measured the worker's history, not the stream. The same helper, duplicated, sits in `test_sqlalchemy_repository.py`'s repository-stream proof and had the same exposure. The negative direction also meant a leak of the same size would pass.

## Fix
`tests/market_data_watch.py::MarketDataWatch` holds what existed when it was created (so it cannot be released nor its ids reused) and counts only live objects created afterwards. Both proofs use it; every assertion is kept (`peak <= chunk size` / `< total_rows // 2`, `final == 0`). Two small tests lock the watch itself: objects held before it began are never counted, objects created after it are.

## Regression test
- Old measurement against the ordering effect, reproduced in isolation (30 objects held, released mid-measurement): old count `-30`, new watch `0`.
- Planted leak, the BUG-025 path: `PythonBinanceClient._stream_raw_klines_as_market_data` temporarily changed to append every chunk to a module list. The proof goes red: `assert 5000 <= 1000`. Source restored; the diff of `src/` is empty.
- `test_the_watch_ignores_market_data_that_existed_before_it_began` and `test_the_watch_counts_market_data_created_after_it_began_while_it_lives`.

## Second observation (not fixed here, not the same mechanism)
A local `tests/unit -n 2` and `-n 3` run failed `tests/unit/modules/bots/ui/bots_screen/test_bots_selection.py::test_the_chart_and_every_panel_follow_the_selection`: the bot log widget held `Bot a00001 placed level 3` plus later `INFO Bot a00001 chart: Syncing BTCUSDT data…` lines, so the exact-text assertion lost a race with the chart's asynchronous load messages. That is a timing race in what the log shows, not a count of heap objects. It failed at `-n 2`, `-n 3` and `-n 6` and passed at `-n 4`, the worker count of the CI command. Needs its own record if it recurs.

## Verification
Both proofs and the watch tests pass locally; the commit tier and CI: see PR #422.
