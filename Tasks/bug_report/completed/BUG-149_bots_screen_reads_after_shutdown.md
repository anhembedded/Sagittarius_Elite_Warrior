# BUG-149 — A bot write queued at shutdown makes the Bots screen submit into a pool that has shut down

- **Reported:** 2026-10-05 (GitHub Actions `ci-local.ps1 -Full` run 37282507866 on PR #356, relayed by the coordinating session)
- **Severity:** 🟢 P3. A test failed once and passed on a re-run. In the app the same race can raise one `RuntimeError` on a pool thread's caller while the window closes; no data is lost.
- **Status:** ✅ Fixed (2026-10-05)
- **Context:** Bots screen journey (`Docs/SPEC/`, the Bots use cases) → `src/modules/bots/` → `ui/bots_screen/` (`bots_presenter.py`, `fenced_reads.py`)
- **Environment:** GitHub Actions Linux runner, `QT_QPA_PLATFORM=offscreen`, `pytest-xdist`; app `2ac8c0f`'s parent on PR #356, engine at `engine.ref`.

## Reproduction

Timing-dependent; seen once in CI. On one xdist worker, `tests/integration/modules/bots/test_bots_tab_drives_the_executor.py` ran first, then `tests/integration/modules/bots/test_grid_backtest_stored_klines.py` failed. A re-run passed.

Deterministic form: a bot is saved from a thread other than the Qt thread, so its `BotChangedEvent` reaches the screen as a queued delivery. Dispose the presenter, then let the event loop run. Expected: nothing of the closed screen runs. Actual: the queued change re-arms the coalesced re-read, which fires 150 ms later and submits a list read.

## Symptom

pytest-qt caught, in the second test:

```
RuntimeError: cannot schedule new futures after shutdown
  src/modules/bots/ui/bots_screen/fenced_reads.py:111  BotQueries.bots
  -> FencedReads.read -> IThreadManager.submit
```

Expected: a closed screen reads nothing.

## Root cause

- `BotsPresenter._connect` wired `self._changes.changed.connect(lambda *_: self._reread.start())`.
- `BotChangesFeed` reaches the Qt thread through the engine's `QtEventBridge`. A write on another thread (a bot's worker, a use case on the pool) is delivered queued. `BaseFeed.stop()` unsubscribes from the bus, but a delivery already posted still runs.
- `BotsPresenter.shutdown()` stopped `_reread`. A change delivered after that started it again: the lambda could not know the screen had closed.
- When the timer fired, `BotQueries.bots()` called `FencedReads.read()`, which never checked that `drop_all()` had run. It submitted into the app's pool, which the previous test's teardown had already shut down.
- No net covered it. The unit tests dispose the screen and then run the held pool; none delivers a queued change after dispose. No case study: the blind spot is this screen's, and the scan below found no other coalescing timer in `src/`.

## Fix

- `fenced_reads.py`: `drop_all()` is final. It sets a flag, and `read()` refuses every later read with a debug log, before the pool is touched. This guards every path into the read seam, not just the change feed.
- `bots_presenter.py`: the change handler is the bound method `_on_bot_changed`. After `shutdown()` it logs at debug and arms nothing.
- Scan of the bots UI for the same shape:
  - `GridBacktestCoordinator` already refuses work after `close()`.
  - `BotActionsCoordinator.send` is reached only from a user action, and its answers are fenced by the action tracker.
  - `BotTickFeed` and `BotLogFeed` deliveries after shutdown touch only the model, never the pool.
  - `single_shot_timer` has no other user in `src/`.

## Regression test

- `tests/unit/modules/bots/ui/bots_screen/test_fenced_reads.py::test_a_read_asked_after_drop_all_never_reaches_the_pool`. It failed before the fix: the read was submitted (`pool.pending` held one task). It passes after.
- `tests/unit/modules/bots/ui/bots_screen/test_bots_presenter.py::test_a_write_still_queued_when_the_screen_closes_arms_nothing`. A real store write from a `threading.Thread` puts a real queued delivery through the real `QtEventBridge`. It failed before the fix: the presenter's re-read `QTimer` was active after dispose. It passes after.
- Mutation check: restoring either file alone turns its own test red.

## Verification

- Both tests green; `tests/unit/modules/bots/ui` green (110 passed).
- Positive proof: the presenter test logs `App.Bots.Screen DEBUG Bots screen: a bot change after shutdown is ignored`.
- The CI pair `test_bots_tab_drives_the_executor.py` then `test_grid_backtest_stored_klines.py` passed three times in a row locally.
- Commit tier (`ci-local.ps1 -SkipTests`, architecture tests) green before the commit.
