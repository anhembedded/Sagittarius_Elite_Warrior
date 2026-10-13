# BUG-200 — A Grid start halts with `start_refused` because the exchange's history read ends before the opening buy's last slice

- **Reported:** 2026-10-13 (master push run 38281947409 after #470, job `gate (Rest)`: `test_a_running_bots_orders_are_quoted_in_its_venues_filters` timed out in `waitUntil` after 10 000 ms; it passed on #470's own runs)
- **Severity:** 🟡 P2 — a Grid start can halt after the opening buy was paid for, on a loaded machine or a slow link; it is recoverable (Resume or Stop) but needs the user, and it reddens CI at random
- **Status:** ✅ Fixed (2026-10-13)
- **Board:** The bots-tab timeout was not slowness: the bot was HALTED (`start_refused`), because a history read's window ended at the machine's estimate of the exchange's "now", which is wrong by up to half a round trip, so the opening buy's last slice was stamped after the window and the inventory derived from the read was short by it; fixed by making the last window of every history read reach 5 s past that estimate.
- **Context:** Bots → Grid executor start (`src/modules/bots/application/services/grid_start_sequence.py`) → Trading → order history reads (`src/modules/trading/adapters/binance/history_window.py`, used by the Spot and Futures history readers)
- **Environment:** GitHub Actions `ubuntu-latest` (4 cores shared by xdist workers); reproduced on a 4-core Linux container with 6 busy loops competing. Fake exchange on loopback.

## Reproduction
1. `pytest tests/integration/modules/bots/test_bots_tab_drives_the_executor.py -n 4` while six busy loops compete for the four cores.
2. Before the fix, in one loop of ten such runs, five failed (one or two of the file's six tests each; the named test failed in two of the ten, the others at the same `wait_for`); alone, the test passes in 2.7 s.
3. The wait that expires is `screen.wait_for(bot_id, RUNNING)` (line 193 in the failing file at that commit), not the orders wait the traceback's `waitUntil` could also be.

## Symptom
CI: `pytestqt.exceptions.TimeoutError: waitUntil timed out in 10000 milliseconds`. Local probes at the moment of timeout, none of them a slow worker (every pool thread idle, a thread dump at 7 s shows nothing running):
```
bot state: BotLifecycleState.HALTED
App.Bots.GridExecutor - INFO - Bot hm28fk: STARTING -> HALTED on start_refused (start_refused: the opening buy is not in the exchange's record: the exchange's record of the opening buy holds 0.01598400 BTC, the ladder's SELLs need 0.02397; nothing was laid)
App.Trading.OwnerInventory - INFO - Derived inventory for hm28fk on BTCUSDT: 0.01598400 BTC at cost 800.00000000 (from a checkpoint, 2 order(s)).   <- three slices were bought
```
A probe on the fake exchange's `allOrders` in a failing run: `{"query_end_lag_ms": 28, "orders_after_end": [4], "returned": 2}` — the request's `endTime` was 28 ms behind the exchange's clock and one order was stamped 4 ms after it.

## Root cause
`SpotHistoryReader.order_history` / `trade_history` (`spot_history_reader.py:125-160`) and the Futures reader's three reads end their window at `span_ms(since, now, client.timestamp_offset)`: the machine's `now` plus an offset measured **once** at session creation from the midpoint of one round trip (`binance_client_builder.py:87-100`). The midpoint is exact only when both legs took equally long; under load they do not, and the estimate is wrong by up to half the trip (28 ms seen). A window that ends at the estimate can end before an order the exchange stamped a moment ago. The opening buy is exactly that: `GridStartSequence._count_opening` (`grid_start_sequence.py:150-190`) registers the budget immediately after the last slice returns, `OwnerInventoryDeriver.derive` (`owner_inventory_deriver.py:113-117`) replays only the orders the read lists, and a shortfall against the ladder's SELLs is `start_refused`, halting a bot that has already bought.

It is a product defect that CI exposed, not a test flake: the same read follows every order the app places on a real exchange. Why it surfaced after #470 is not established and I did not bisect. The candidate in the brief, the health publisher with its 10 s interval and new subscribers, appears nowhere in the failing runs' logs or thread dumps; the failure needs only a read that ends early, and any added load on the runner widens that.

## Fix
`history_window.py`: `fetch_span` takes the last window `rules.last_window_margin_ms` (default `LAST_WINDOW_MARGIN_MS`, 5 s) past `until_ms`; the start of the read, and the Futures `max_age_ms` clamp, are computed from the unpadded `until_ms`, so nothing about how far back a read reaches changes. The exchange holds no row stamped in the future, so asking past "now" returns no extra rows. It is in `fetch_span`, the one function every Spot and Futures history read goes through (orders, trades, algo orders, income), not at the call sites.

## Regression test
- `tests/integration/infrastructure/binance/test_history_readers_against_fake_server.py::test_a_spot_order_placed_a_moment_ago_is_in_the_read_whatever_the_clock_error` and `::test_a_futures_order_placed_a_moment_ago_...`: the real readers over HTTP to the fake exchange, a session whose offset was measured 1 s low (exchange clock skewed during the measurement, asserted), an order placed, then read back. Red before the fix: `assert [] == ['SEW-hist-fresh-spot']` (resp. `...-fut01`); green after.
- `tests/unit/modules/trading/adapters/binance/test_history_window.py::test_the_last_window_reaches_past_until_by_the_margin_and_a_row_there_is_read`.
- Three unit tests that pinned the end of the window to the exact estimate now pin it to the estimate plus the margin (`test_history_readers.py`, `test_history_readers_machine_clock.py`); the same assertions about the start are unchanged.

## Verification
- Before: in one loop of ten runs of the file under CPU contention, five failed; after the fix: 20 of 20 runs passed under the same contention, and the probe on the fake's `allOrders` recorded no order past a window's end.
- `tests/integration/infrastructure/binance` and `tests/unit/modules/trading`: 2609 passed.
- Not established: that nothing else makes the bots tab slow after #470. The wait itself was not changed.
