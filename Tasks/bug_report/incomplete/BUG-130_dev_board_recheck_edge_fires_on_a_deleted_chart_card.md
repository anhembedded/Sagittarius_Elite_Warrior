# BUG-130 — Dev Board's arm-strategy integration tests time out; `_recheck_edge` fires on a deleted `ChartCard`

- **Reported:** 2026-09-17 (found while driving EPIC-025 PR #226 to green; confirmed pre-existing and unrelated to that PR by reproducing on `origin/master-warrior`'s own tip, commit `9a0888cf`, before any PR #226 code was applied)
- **Severity:** 🟡 P2 — two integration tests time out (2000ms `waitUntil`) rather than crash the app; blocks nothing user-facing yet observed, but the log-scan `ERROR` it produces fails `ci-rule.md` §8's gate on every run that exercises this path
- **Status:** Open — reproduced and the mechanism is a well-evidenced candidate, not yet proven by a fix

## Symptom
Two integration tests under `tests/integration/presentation/ui/` fail with a `pytestqt.exceptions.TimeoutError`:

```
FAILED tests/integration/presentation/ui/test_dev_board_known_gaps.py::test_strategy_dropdown_arms_the_selected_strategy - pytestqt.exceptions.TimeoutError: waitUntil timed out in 2000 milliseconds
FAILED tests/integration/presentation/ui/test_dev_board_manual_order_qt_click.py::test_a_real_long_click_on_the_armed_symbol_reaches_the_real_pipeline - pytestqt.exceptions.TimeoutError: waitUntil timed out in 2000 milliseconds
```

Alongside them, the run-log scan (`ci-rule.md` §8) sees a real `ERROR` record, which fails the gate on its own:

```
2026-09-17 12:58:29,981 - App - ERROR - [UI Thread Bridge Error] Exception in _recheck_edge: Signal source has been deleted
2026-09-17 12:58:29,981 - App - ERROR - [system-failure] UI error in _recheck_edge: RuntimeError: Signal source has been deleted
2026-09-17 12:58:29,981 - App - ERROR - [system-failure] _recheck_edge detail:
Traceback (most recent call last):
  File ".../sagittarius_engine/extensions/pyside_mvc/safety/thread_bridge.py", line 33, in wrapper
    return func(*args, **kwargs)
  File "src/presentation/ui/screens/dashboard/dashboard_presenter.py", line 1791, in _recheck_edge
    card.check_near_left_edge()
  File "src/support/charting/chart_card/chart_card.py", line 323, in check_near_left_edge
    self.edge_scroll_detector.check_edge()
  File "src/support/charting/chart_card/edge_scroll_detector.py", line 59, in check_edge
    self.sig_near_left_edge.emit()
RuntimeError: Signal source has been deleted
```

Expected: both tests reach their asserted end state within the timeout, and the run log carries no `ERROR` record.

**Confirmed pre-existing, not caused by EPIC-025 PR #226**: reproduced identically on a clean worktree of `origin/master-warrior`'s tip (commit `9a0888cf`, no PR #226 code) —

```
FAILED tests/integration/presentation/ui/test_dev_board_known_gaps.py::test_strategy_dropdown_arms_the_selected_strategy
FAILED tests/integration/presentation/ui/test_dev_board_manual_order_qt_click.py::test_a_real_long_click_on_the_armed_symbol_reaches_the_real_pipeline
2 failed, 1 warning in 9.21s
```

## Root cause
Candidate mechanism, not yet proven by a fix — `src/presentation/ui/screens/dashboard/history_pagination_controller.py:60-65`'s own docstring already names half of this lifecycle concern and answers it for the *controller's own* timer:

> "Outstanding recheck timer per symbol, parented to `self` — a `QTimer(self)` (not the static `QTimer.singleShot`) so Qt's parent-child ownership cancels it automatically if this controller is destroyed mid-cooldown ... instead of firing into a torn-down object graph later."

That protects against the *controller* dying first. It does not protect against the **card** dying first while the controller (owned at `DashboardPresenter` scope, longer-lived) is still alive: `_on_cooldown_finished()` (line 122) fires the timer's `timeout` into `DashboardPresenter._recheck_edge(symbol)` (`dashboard_presenter.py:1787`), which does:

```python
card = self.active_charts.get(symbol)
if card:
    card.check_near_left_edge()
```

`active_charts.get(symbol)` finding a truthy `card` proves the *Python* wrapper is still reachable from the dict — it does not prove the underlying Qt/Shiboken C++ object is still alive. `ChartCard.check_near_left_edge()` (`chart_card.py:323`) reaches `EdgeScrollDetector.check_edge()` (`edge_scroll_detector.py:59`), which emits `sig_near_left_edge` on a `ChartCard` whose C++ side has already been deleted — the exact "Signal source has been deleted" `RuntimeError` PySide6 raises for a dangling wrapper. `@safe_ui_action` (line 1786) swallows the exception into a logged `ERROR` rather than letting the test see an assertion failure directly, which is why the symptom is a *timeout* (the awaited UI state never arrives) rather than a crash.

Not yet identified: **why** `active_charts` still holds this symbol's entry pointing at a deleted card at the moment the cooldown timer fires. `active_charts` is only rebuilt wholesale via `.clear()` + repopulate (`dashboard_presenter.py:1673-1683`); nothing found so far removes a single symbol's entry when just that one card is torn down (e.g. the dropdown's strategy-arm flow swapping the active symbol's chart, or test teardown destroying widgets while a cooldown timer from an earlier interaction in the same test is still pending). That gap — not the timer's own lifetime, which is already handled — is where the next session should look.

## Fix
Not yet attempted. Two candidate shapes, for the next session to weigh against `async-ui-action-rule.md` §1 rather than picking blindly:
1. `_recheck_edge` (or `active_charts.get`) checks the card is still a live Qt object before touching it (e.g. via `shiboken6.isValid(card)`), mirroring the "receiving slot verifies the action is still active" rule already required for background-action callbacks.
2. Whatever destroys/replaces a single `active_charts[symbol]` entry also stops that symbol's outstanding recheck timer in `HistoryPaginationController` — closing the actual gap, general over local (`bug-fix-rule.md` §2), rather than guarding every reader of `active_charts` individually.

## Regression test
Not yet written. Candidate tier: an integration test that arms a strategy (or otherwise triggers a near-left-edge fetch + cooldown) on one symbol, replaces or removes that symbol's `ChartCard` before the cooldown timer fires, then advances past the cooldown and asserts **no** `ERROR` reaches the log — the two existing failing tests already reach this path but were not written to pin the mechanism, only to observe a downstream symptom (their own `waitUntil` promise).

## Suggested next steps
1. Trace every place `active_charts[symbol]` is written or a `ChartCard` is destroyed (not just the wholesale `.clear()` rebuild) to find the gap between "card destroyed" and "cooldown timer stopped".
2. Reproduce deterministically (not via the two integration tests' own incidental timing) with a focused unit/integration test that controls the cooldown timer directly, per `testing-rule.md` §2's "no timing sleeps" — drive the timer's `timeout` synchronously rather than waiting on the real 2000ms.
3. Fix at the mechanism (candidate 2 above is the more general one), write the regression test first per `bug-fix-rule.md` §4, confirm it fails for this exact reason before changing any production code.
