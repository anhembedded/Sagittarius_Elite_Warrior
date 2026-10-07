# BUG-171 — `gate (Rest)` failed once at the teardown of `test_a_buy_opens_the_closed_session_and_is_sent`: "cannot schedule new futures after shutdown"

- **Reported:** 2026-10-07 (the `EPIC-034` PR-3 session, CI run 37592720010 attempt 1, job 112697817113; the coordinator asked for it to be filed and fixed)
- **Severity:** 🟡 P2 — an intermittent red `gate (Rest)` on any PR; passes on a re-run, so it costs a cycle and hides real reds
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** The Trade-mode integration harness stopped its worker pool before delivering the workers' answers, so an order's answer still on its way when a test ended made the order panel read again on a stopped pool (`RuntimeError: cannot schedule new futures after shutdown` in the Qt loop). Fixed: the harness runs the workers dry, delivering each answer, before it stops the pool (`trade_mode_boot.settle_workers`).
- **Context:** `tests/integration/presentation/ui/` harness → `src/modules/trading/ui/desk/order_entry/order_entry_presenter.py` (`_on_submitted`) → tests only
- **Environment:** GitHub Actions `ubuntu-latest`, Python 3.12.14, `pytest-xdist` workers (`gw0`), Qt `offscreen`; app head `a7db981` of PR #417. Not reproduced by 25 sequential local runs of the file.

## Reproduction
Not seen locally in 25 runs: the failure needs the order's answer to still be on its way when the test body ends. Made deterministic by holding the order at the venue: `tests/integration/presentation/ui/test_trade_mode_against_fake_server.py::test_closing_the_desk_with_an_order_in_flight_leaves_no_qt_error`.

## Symptom
From the artifact `ci-local-logs-Rest` of the failed attempt (the job log's grep shows only line numbers; the body is in the artifact):
```
ERROR at teardown of test_a_buy_opens_the_closed_session_and_is_sent
TEARDOWN ERROR: Exceptions caught in Qt event loop:
  order_entry_presenter.py, line 365, in _on_submitted: self.refresh()
  order_entry_presenter.py, line 175, in refresh:       self._threads.submit(self._run_load, ...)
  sagittarius_engine/infrastructure/thread_manager.py, line 54, in submit: self._executor.submit(...)
  concurrent/futures/thread.py, line 171, in submit:
RuntimeError: cannot schedule new futures after shutdown
```
The captured teardown log shows `Order panel BUY order: Order placed` first, then `[live-chart] ETHUSDT: CONNECTING -> ERROR on STREAM_FAILED` (the fake server has no websocket; an unrelated, expected line), then the app stopping. The first guess, a live-chart stream failure after teardown (`EPIC-034G`'s state machine), was wrong: that line is only what the chart says on the way down.

## Root cause
`tests/integration/presentation/ui/trade_mode_boot.py` (the `finally` of `trade_mode_running`) called `threads.shutdown(wait=True)` and only then `qapp.processEvents()`. `shutdown(wait=True)` waits for a worker still running, and that worker's `_submitted` signal is queued to the UI; `processEvents()` then delivered it to the stopped pool: `_on_submitted` ends in `self.refresh()`, which submits a load. Whether the answer was delivered earlier (while the test's `qtbot.waitUntil` spun the loop) or only in this `processEvents()` depends on whether the worker had returned from the venue by the time the test saw the order's POST on the fake server: the test returns on that POST, not on the answer. So the same code passes or fails with the scheduler, and the xdist run, loaded by other workers, makes the late answer likelier.

The defect is the harness's order of two steps, not the presenter: any answer that starts more work needs the pool alive, and the app's own shutdown never delivers events after stopping its pool. Scanned for the same pattern: `trade_mode_running` is the only test harness that calls `IThreadManager.shutdown` (`grep -rn "threads.shutdown" tests`); the three test files using it were run together.

No case study: no net covered this and missed it; the red was the net.

## Fix
`trade_mode_boot.py`: `settle_workers(qtbot, threads)` waits for the pool to be idle (`qtbot.waitUntil`, a named condition), delivers what the workers answered, and repeats until delivering starts no more work; the `finally` runs it before `threads.shutdown`. The later `processEvents()` after the shutdown is gone: nothing is left for it to deliver.

Also carried from the `EPIC-034` PR-3 review: `test_module_venue_accounts_binding.py::test_a_source_the_configuration_does_not_enable_has_no_reader` restores the test of `UnknownAccountSourceError` in `VenueAccounts.reader` that the move to always-assembled venues removed.

## Regression test
`tests/integration/presentation/ui/test_trade_mode_against_fake_server.py::test_closing_the_desk_with_an_order_in_flight_leaves_no_qt_error`: holds the Spot order at the venue, releases it as the desk closes, and asserts the Qt loop caught nothing (`qtbot.capture_exceptions`). Red before the fix for the reason above (`RuntimeError('cannot schedule new futures after shutdown')`), green after; red again with the `settle_workers` call removed. The mutation of the unit test (`VenueAccounts.reader` without its source check) is red too.

## Verification
Local, `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen`: the Trade-mode file, six runs in a row, 5 passed each; the three files that use the harness with `-n 4`, passed. The CI re-run attempt is the full-gate evidence (cited on the PR).
