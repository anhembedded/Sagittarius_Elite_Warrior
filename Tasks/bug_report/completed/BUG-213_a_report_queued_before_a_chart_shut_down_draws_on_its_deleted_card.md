# BUG-213 — A live-chart report queued before the chart shut down is delivered onto its deleted card (sanity `market0` fails once in a while)

- **Reported:** 2026-10-15 (the coordinator session: `tests/sanity/test_composition_root.py::test_every_navigable_route_constructs[market0]` failed once on PR #519, a one-Markdown-file change, and passed on the re-run of the same commit)
- **Severity:** 🟡 P2 — a closed Market, desk or bot chart can raise `RuntimeError` in the Qt event loop (a freed `QAction`/`QLabel`/chart item); in the app that is a swallowed slot error, in the gate it is a red run on an unrelated PR. No order or figure is affected.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** A closed chart still took a report queued before it shut down and drew on its freed card (`live_candle_chart.py` slots matched a cancelled token by identity); `shutdown()` now swaps in a token no worker holds, so none of those slots matches a queued report, and `_on_history` returns while the token is cancelled. [BUG-150](bug_report/completed/BUG-150_closed_market_tab_reports_on_its_deleted_chart.md) fenced only the worker side.
- **Context:** [SPEC-002](../../../Docs/SPEC/SPEC-002_watch_the_live_market.md) (watch the live market) → `src/support/charting/live_chart/` (shared by the Market, desk and bot charts) → UI support / worker seam
- **Environment:** GitHub Actions ubuntu-latest, Python 3.12, offscreen Qt, `gate (Rest)` attempt 1 of run 38723177621 (head `6544a53`); reproduced on Linux, Python 3.13, PySide6 6.11.1, `master-warrior` at `981f391`.

## Reproduction
1. A chart is `Connecting` (Go live asked, the worker not yet answered), or has a first window in flight.
2. The worker checks its token (live), emits its report, and the call is queued to the Qt thread.
3. Before the queue is read the Qt thread calls `shutdown()` on the chart and the window's `deleteLater` frees its `ChartCard`; the `LiveCandleChart` is a child of the presenter and stays.
4. The event loop delivers the queued call.

- **Expected:** a shut-down chart ignores it.
- **Actual:** the slot draws on freed widgets: `RuntimeError: libshiboken: Internal C++ object (…) already deleted`.
- **Frequency:** a narrow race in the gate (the worker must pass its token check, and the report be queued, within the few milliseconds before the test's `window.shutdown()`); not reproduced in 48 isolated loops of the failing test, nor 6 runs of the whole file under CPU load. Deterministic once the queued report is made explicit (the regression test).

## Symptom
Attempt-1 job log (`ci-local-logs-Rest` artifact, `logs/ci-local-20261015-105151.log`, no traceback kept by the gate's `--tb`):
```
CALL ERROR: Exceptions caught in Qt event loop:
RuntimeError: libshiboken: Internal C++ object (PySide6.QtWidgets.QLabel) already deleted.
RuntimeError: libshiboken: Internal C++ object (PySide6.QtWidgets.QLabel) already deleted.
FAILED …/test_composition_root.py::test_every_navigable_route_constructs[market0]
```
The regression test shows the same error with its traceback (`QAction` at `live_state_chip.py:100`, the first widget `show_state` touches; the `QLabel` is the next line, `_label.setText`).

Not established: which queued report the CI run delivered, and which `QLabel` it named. Reproductions of the same race name whichever freed object a slot touches first: `QAction` (`live_state_chip.py:100`), `FastCandlestickItem` (`candlestick_item.py:97`), `LogListModel` (`desk_view_model.py:118`, through `chart.logged`). A `QLabel` is reachable from the same slots (`LiveStateChip._label`, `live_state_chip.py:115`; the Desk's status label, `desk_view.py:223`, through `liveStateChanged` → `desk_presenter.py:260`), but no run here produced one.

## Root cause
- `LiveCandleChart.shutdown()` (`live_candle_chart.py`) cancels `self._token` but does not replace it. The slots `_on_stream_opened`, `_on_stream_lost`, `_on_load_lost` and `_on_load_settled` (`live_candle_chart.py`) accepted a report when `token is self._token`, which is still true for the cancelled token; `_on_history` carries no token and checked only the symbol and interval.
- The `LiveCandleChart` is a `QObject` held by its owner (the Market presenter), so it outlives the `ChartCard` the window deletes. A report queued while its request was live is then delivered to a slot that calls `LiveStateChip.show_state` (`live_state_chip.py:100`, `:115`) or `ChartCard.render_historical_data` (`chart_card.py:337`) on freed C++ objects.
- `BUG-150` fenced the worker side (`report_unless_cancelled`, `cancellable_report.py`): nothing is emitted once the token is cancelled. It cannot cover a report emitted before the cancel and delivered after it; the receiving side had no fence.
- Why the gate missed it: `test_live_chart_coordinator.py` and `test_cancellable_report.py` drive the worker side; no test delivered a queued report after a shutdown with a really deleted card. It surfaces in the sanity tier only because that test shuts a window down right after `switch_screen` while the Market's first window and stream are still in flight.

## Fix
- **`live_candle_chart.py`:** `shutdown()` cancels the token and replaces it with a fresh one, cancelled at once. A worker holds the token of its own request, never the new one, so the identity test the four tokened slots already make (`token is self._token`) fails for every report queued before the shutdown, with no edit to the slots; `_on_history`, which carries no token, returns while `self._token.is_cancelled()`. A shut-down chart draws nothing and tells no failure (its bar was cleared by `shutdown()`; a late one would have a Retry for a closed chart). The seam is shared by the Market, desk and bot charts, so all three are fixed; no other receiver in `src/` matches by token identity alone.

- **`logged` fan-out (found while checking the QLabel):** the coordinator's `log` callback was `self.logged.emit`, so a line queued by a worker reached every owner's slot (Desk `desk_presenter.py:256`, Market `market_presenter.py:297`, Bots `bot_chart_host.py:134`) after the window was freed; with the fix above in place a real-window probe still raised `LogListModel already deleted` at `desk_presenter.py:347`. The callback is now `_worker_said`, a queued signal whose slot re-emits `logged` only while the token is not cancelled.
- **`live_stream_action.py` (new):** the Live stream `QAction` and its "mirror without reporting it as the user's choice" flag moved out of `live_candle_chart.py` (at the 400-line ceiling) into `LiveStreamAction`; behaviour unchanged.

## Regression test
- `tests/unit/support/charting/live_chart/test_live_candle_chart_after_shutdown.py::test_a_report_queued_before_shutdown_draws_nothing_on_the_deleted_card[stream opened | stream lost | history]`: a real `ChartCard` and `LiveCandleChart` (owner outside the card), chart `Connecting`, the report emitted from a real thread (so queued), `shutdown()`, the card really freed (`sendPostedEvents(DeferredDelete)`, `shiboken6.isValid` asserted false), then `processEvents()` under `qtbot.capture_exceptions()`. No sleep.
- Red before the fix, all three, with `RuntimeError: … already deleted` at `live_state_chip.py:100` (stream) and `candlestick_item.py:97` (history). Green after.
- `…::test_a_line_queued_before_shutdown_does_not_reach_the_owners_freed_log`: a consumer object freed with the card, a line queued from a real thread; red when `_on_worker_said`'s gate is removed.
- Mutation: removing the token swap in `shutdown()` turns the two stream cases red; removing `_on_history`'s `is_cancelled()` turns the history case red.

## Verification
- `tests/unit/support/charting`, `tests/unit/modules/trading/ui`: 1040 passed. `tests/sanity/test_composition_root.py`: 17 passed. The commit tier and the PR's `-Full` run are recorded on the pull request.
- Not verified: the CI failure itself was not reproduced (race too narrow), so "this is the delivery the run hit" rests on the identical exception class in the identical screen and on the mechanism being the only receiver path with that shape.
