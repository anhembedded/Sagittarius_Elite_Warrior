# BUG-118 — unit UI tests never give their Qt objects back, and the gate stalls

- **Reported:** 2026-09-14 (by the user, mid-`EPIC-025` PR 0.4a-2: *"fix tại sao nó treo"*)
- **Severity:** High — the mandatory commit gate cannot be run to completion, so nothing can be
  verified, committed or merged.
- **Status:** ✅ Fixed 2026-09-14 — root-caused by measurement, reproduced, regression-tested,
  verified by a 91% drop in peak resident memory.

---

## 1. Symptom

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` reached **96%** and stopped making progress.
No test reported `FAILED`; no traceback; no `INTERNALERROR`. It happened on two consecutive runs.

The console named a test each time, and the name was a red herring:

| Run | Last test started, never finished |
| :-- | :--- |
| gate5 | `tests/unit/application/use_cases/trading/test_arm_strategy.py::test_an_unknown_strategy_key_is_named_not_crashed_on` |
| gate6 | the same one |
| gate7 | `tests/unit/shell/test_config_writer.py::test_set_then_save_reaches_the_file` |

The first of those is three statements long — construct a handler, `execute()`, assert — with no
threads, no Qt and no I/O, and it passes **green in 2 seconds** on its own:

```
$ pytest tests/unit/application/use_cases/trading/test_arm_strategy.py -q
9 passed in 1.97s
```

That the third run named a *different* test settled it: the named test is simply whichever one was
in flight when the worker stopped, not the cause.

What the process table showed instead:

```
  PID  %CPU     RSS  COMMAND          (gate6, at the 59% mark)
16214  94.4  3440856 python3.12       <- 3.4 GB, one xdist worker
16211  96.0  3322016 python3.12       <- 3.3 GB, another
16208  13.6   303340 python3.12
16205  26.3   437364 python3.12
```

Two of four workers holding **6.8 GB between them** on a 16 GB box with **no swap**
(`Swap: 0 0 0`). `oom_kill 0` in `/proc/vmstat` — the kernel never killed anything, so this was
not a crash. It was an exhausted machine thrashing, which from the outside is indistinguishable
from a hang.

## 2. Root cause

**Every unit UI test leaks 20-30 MB, and nothing ever gives it back.**

Measured rather than guessed: a throwaway pytest plugin recorded `VmRSS` after each test. No single
test is expensive — the growth is uniform across the presenter tests:

```
  2743 MB  +    30 MB  tests/unit/presentation/ui/screens/test_backtest_presenter.py::test_changing_the_current_page_recomputes_the_trade_log
  2696 MB  +    29 MB  tests/unit/presentation/ui/screens/test_backtest_presenter.py::test_changing_the_filter_resets_to_page_1
  2612 MB  +    25 MB  tests/unit/presentation/ui/screens/test_backtest_presenter.py::test_successful_run_populates_the_trade_log_first_page
   741 MB  +    27 MB  tests/unit/presentation/ui/screens/test_dashboard_presenter.py::test_the_toolbars_more_button_opens_the_full_picker_on_a_real_dev_board_card
```

**Why it is retained.** A presenter test constructs its real view —
`view = BackTestView()` (`tests/unit/presentation/ui/screens/test_backtest_presenter.py:255`,
`:458`, `:525`) — and each is a `QmlHostView`, so each builds a `QQuickWidget` with its own QML
engine. The fixture holding it goes out of scope when the test ends, and the object still does not
die, because a Qt view is a **graph, not a tree**: the view holds its view-model, the view-model's
signals hold the view's slots, and the presenter sits on both sides. That is a reference **cycle**,
and CPython cannot free a cycle by refcounting — only the cyclic collector can, and it runs on its
own generational schedule. Between collections the cycles pile up, each pinning a QML engine.

Verified directly, with the automatic collector disabled to remove its timing from the result:

```
cycle, refcount only : ALIVE (leaked)
cycle, after release : dead
```

**Why nothing cleaned up.** `tests/unit/presentation/` had **no `conftest.py` at all**. This tier
uses no `qtbot`, so nobody calls `deleteLater()`, and nothing pumps the Qt event loop between
tests. The integration tier already hit the other half of this problem — there the deletions *were*
queued and got processed at a dangerous moment, which is `BUG-056` — and its fix is the pair of
calls this one reuses.

**Why it surfaced now.** The leak is old. `EPIC-025` PR 0.4a added ~30 test files and moved ~30
more, which changed how xdist distributes work, so for the first time **two** workers each drew a
large share of the UI presenter tests and climbed to ~3.4 GB at the same time. The gate passing
before (4163 tests green) was luck, not safety.

## 3. Fix

`tests/unit/presentation/qt_object_release.py` — one function, `release_qt_objects()`:

1. `gc.collect()` — break the cycles, which is what drops the Python wrappers, which is what queues
   the underlying C++ deletions;
2. `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` + `processEvents()` — run those
   deletions now instead of carrying the queue into the next test.

The order is not interchangeable: draining first would drain an empty queue and then fill it.

`tests/unit/presentation/conftest.py` — an **autouse** fixture calling it after every test in the
tier, so no test opts in and none can forget. Scoped to this directory: the integration tier owns
engine and thread lifetimes too and must not have a second mechanism pumping underneath it
(`BUG-056`).

Why this is the mechanism fix and not a hotfix (`bug-fix-rule.md` §2): the alternative was to make
each of ~2100 UI tests tear down its own view, which is N copies of one concern and would be missed
by the next test written. One autouse fixture at the tier boundary serves every current and future
test in it for free.

## 4. Regression test

`tests/unit/presentation/test_qt_object_release.py`, three tests:

| Test | Asserts |
| :--- | :--- |
| `test_a_reference_cycle_holding_a_widget_survives_refcounting` | the failure itself — dropping every reference is **not** enough |
| `test_release_qt_objects_collects_that_cycle` | the fix — one call frees what the test above proves is otherwise kept |
| `test_release_qt_objects_is_safe_to_call_twice` | the autouse fixture may run after a test that created nothing, or that already called it |

**Confirmed red before the fix**, as `bug-fix-rule.md` §4 requires — by removing `gc.collect()`
from the helper and re-running:

```
E  AssertionError: release_qt_objects() no longer frees a cycle holding a QWidget —
   the BUG-118 leak is back, and the gate will stall again once enough UI tests run in one worker
FAILED tests/unit/presentation/test_qt_object_release.py::test_release_qt_objects_collects_that_cycle
1 failed, 2 passed
```

and green with it restored: `3 passed in 0.90s`.

**A first attempt was thrown away, and why it mattered.** It asserted that
`weakref.ref(BackTestView())` dies after the release — and it **passed without the fix**, because
an acyclic widget is freed by refcounting the moment its last reference goes. It would have been a
test that proves nothing, the same trap `BUG-013` fell into. The reproduction had to name the
*cycle*, which is what the real views form.

## 5. Verification

| Measure | Before | After |
| :--- | :-: | :-: |
| Peak RSS, `test_backtest_presenter.py` alone (164 tests) | **2.86 GB** | **258 MB** |
| RSS growth across those 164 tests | ~2.6 GB | **32 MB** |
| Worker peak at the 23% mark of the full gate | 3.4 GB | **381 MB** |
| `tests/unit/presentation`, 4 workers | (thrashing) | 2100 passed in 126 s |

Measured with the same command and the same worker count in both columns; the only difference is
whether `tests/unit/presentation/conftest.py` is present.

## 6. What this bug also exposed

Two findings that came out of the investigation and are **not** part of this fix:

- **The gate's console output cannot name the cause of a stall.** It names the test in flight, which
  three runs proved is arbitrary. `py-spy dump` on the controller and the workers is what actually
  answered it (controller in `xdist/dsession.py:154` waiting on its queue, all four workers idle in
  `execnet` `serve()`). Worth remembering the next time the gate goes quiet rather than red.
- **A stall is not always memory.** Even after this fix the first full run still did not finish, with
  workers at 1.8 GB rather than 3.4 GB — there is a separate, intermittent xdist scheduling stall
  that this bug does not explain and does not claim to. It is recorded as its own item rather than
  folded in here, because attributing it to the leak would be a guess.
