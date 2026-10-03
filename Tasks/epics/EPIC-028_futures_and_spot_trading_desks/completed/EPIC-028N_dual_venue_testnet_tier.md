# EPIC-028N — One real round trip on each desk, in the same process, on Testnet

**Status:** ✅ Done (2026-10-03)
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — touches two real testnets at once; must never make regular CI red
**Complexity:** S — extends the existing opt-in tier
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028K](EPIC-028K_futures_desk_screen.md), [EPIC-028L](EPIC-028L_spot_desk_screen.md)

---

## 1. Context and problem
- `tests/testnet/` proves Futures and Spot round trips separately, each in a single-venue process (EPIC-027P).

## 2. Acceptance criteria
- [x] With `SEW_TESTNET_TESTS=1` and both key pairs, one test process opens a Futures position and closes it and buys then sells Spot, through `IVenueContexts`, and both return to baseline. The user's run on 2026-10-03 passed: `test_one_process_trades_both_venues_back_to_baseline PASSED` (§5).
- [x] Without the flag or either key pair it skips with a stated reason: `missing SEW_TESTNET_TESTS=1 …`, or `… no futures_testnet credentials were found` / `… no spot_testnet credentials were found`.
- [x] The user's run is pasted into this task file (§5).

## 3. Design
- **The composed path, not hand-built adapters.** The test builds `create_app()` with `exchange.trading_venues = ["futures_testnet", "spot_testnet"]` and takes both venues from the container's `IVenueContexts`: client factory, account reader and metadata provider. The app reads the keys itself (environment first, then `src/config/secrets.local.json`). The app is built but not booted: `create_app()` already binds every venue's ports, and booting would start market streams and user-data websockets the test does not need.
- **One round-trip body for three tests.** `tests/testnet/round_trips.py` holds `futures_open_and_close()` and `spot_buy_and_sell()` against ports (`ITradingClient`, `ITradingAccountReader`, `IMarketMetadataProvider`). `test_order_lifecycle.py` and `spot/test_spot_order_lifecycle.py` now call them with their hand-built adapters, and the new test calls them with the composed ones. The waits, residue bound and `finally` clean-ups are unchanged, moved rather than copied.
- **One credentials gate.** `resolve_testnet_credentials(venue)` in `tests/testnet/conftest.py` serves both `testnet_credentials` and `spot_testnet_credentials`. The second fixture moved up from `spot/conftest.py` (deleted) so the dual-venue test in the tree root can use both.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/testnet/test_dual_venue_round_trip.py` | new: both venues from `IVenueContexts`, one process |
| `tests/testnet/round_trips.py` | new: the Futures and Spot round trips, shared |
| `tests/testnet/test_order_lifecycle.py`, `spot/test_spot_order_lifecycle.py` | call the shared round trips |
| `tests/testnet/conftest.py` | one gate for both venues; `spot_testnet_credentials` moved here |
| `tests/testnet/spot/conftest.py` | deleted (its fixture moved up) |

## 5. Testing
The user runs `ci-local.ps1 -TestnetOnly`; output pasted here.
- **Skip paths (this sandbox):** without the flag, all 5 tests of the tree skip with `missing SEW_TESTNET_TESTS=1`. With the flag and no Futures key, they skip naming `futures_testnet`.
- **Rehearsal (this sandbox, not committed):** a scratch pytest plugin pointed `Client.API_TESTNET_URL` / `FUTURES_TESTNET_URL` at `run_binance_fake_server()` with fake keys. `test_dual_venue_round_trip.py`, `test_order_lifecycle.py` and `spot/test_spot_order_lifecycle.py` then gave **4 passed**. This proves the test code and the composed wiring, not Binance's real filters.
- **Real run (the user, 2026-10-03, Windows, `master-warrior` after PR #312):** `pwsh -NoProfile -File scripts/ci-local.ps1 -TestnetOnly`, with both key pairs in the environment.
  ```
  ===CI_LOCAL_RESULT===
  RESULT: PASS
  FAILED_STEPS: none
  LOG_FILE: ...\logs\ci-local-20261003-140941.log
  ===END_CI_LOCAL_RESULT===

  tests\testnet\spot\test_spot_order_lifecycle.py::test_market_buy_then_sell_returns_the_holding_to_baseline PASSED [ 20%]
  tests\testnet\test_connection.py::test_account_is_reachable PASSED [ 40%]
  tests\testnet\test_dual_venue_round_trip.py::test_one_process_trades_both_venues_back_to_baseline PASSED [ 60%]
  tests\testnet\test_order_lifecycle.py::test_dry_run_is_accepted PASSED [ 80%]
  tests\testnet\test_order_lifecycle.py::test_market_order_fills_and_closes PASSED [100%]
  ============================= 5 passed in 17.36s ==============================
  ```
  All five ran rather than skipped: the run log lists each as `PASSED`. `RESULT: PASS` alone would not show this, because a skipped tier also passes. This is also the first real run of the Spot round trip since `EPIC-027P`, so its quantity (`0.0002` BTC) and step bound hold against the live Testnet filters.

## Implementation notes (written when done)
- The composed app resolves `IVenueContexts` before `boot()`, and logs `Trading venues enabled: ['futures_testnet', 'spot_testnet']; primary venue: futures_testnet.` `app.stop()` without a boot is clean.

## Resume
Done. Nothing to resume.
