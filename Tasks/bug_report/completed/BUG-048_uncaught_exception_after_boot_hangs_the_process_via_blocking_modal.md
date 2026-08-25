# BUG-048 — Any uncaught exception after boot hangs the process forever via a blocking modal dialog

**Reported:** 2026-08-25, found while validating `EPIC-009`'s new
out-of-process Sanity test (`tests/sanity/test_self_check_process.py`) against
a deliberately injected fault — not a hypothetical, reproduced twice with
direct evidence.
**Severity:** 🔴 **P1** — the failure mode is worse than a crash: the process
does not exit at all, indefinitely, with zero indication anything is wrong
short of watching it never terminate. A crash is visible; this is silent.
**Status:** ✅ **Fixed 2026-08-25**

## Symptom

Any exception that reaches `sys.excepthook` — installed by
`_install_exception_handler()` (`app_bootstrapper.py:249-269`) — triggers this
handler:

```python
def _handler(exc_type, exc_value, exc_tb) -> None:
    ...
    dialog = CriticalErrorDialog(...)
    dialog.exec()          # <- blocks until dismissed
```

`QDialog.exec()` is modal and blocking: the calling code does not proceed
until a human closes the dialog. Under `QT_QPA_PLATFORM=offscreen` — required
for headless CI, and the platform every automated test on this project runs
under — **nothing can ever close it**. There is no window manager, no user, no
input event that reaches an offscreen dialog. The process hangs until an
external `timeout` kills it (or forever, with none).

## Reproduction

Injected two probes into `teardown()` in `app_bootstrapper.py` (not committed
— reverted after each), both under `--self-check`:

1. **Raise before any teardown step runs.** Result: process hangs; killed by
   an external 30s timeout; `subprocess.TimeoutExpired`.
2. **Raise after `app_engine.stop()` completes** (log confirms `"App
   stopped."` was reached first). **Same result — the process still hangs**,
   confirmed by direct process inspection (`ps` showed the interpreter alive
   and unresponsive well past the point where all application-level teardown
   had already finished cleanly).

The second probe is the important one: it proves the hang is **not** caused by
teardown being interrupted or leaving a background thread alive (the original
hypothesis). `app_engine.stop()` — the step that stops the background
`AsyncRuntime` thread — had already completed. The hang is caused purely by
`sys.excepthook`'s own fallback UI, independent of application shutdown state.

## Why this matters beyond `--self-check`

`--self-check` only exposed it because it made the process boundary
observable for the first time. The defect is not in `--self-check` and is not
new — `_install_exception_handler` has looked like this since before this
session. Any of the following, in the real running application, would hang
the process the same way:

- an exception in a `QTimer.singleShot` callback after the main window starts
  closing;
- an exception during `MainWindow.closeEvent`'s cooperative shutdown path;
- any exception on the main thread between `build()` returning and
  `teardown()` finishing — a window that previously had no test coverage at
  all (see `EPIC-009`).

A user hitting this today would see the app "freeze" with no error dialog
visible (nothing is there to make one visible outside a real windowing
session with an interactive user) — indistinguishable from a generic hang,
and a strong candidate for at least one of the shutdown-hang bugs already on
record (`BUG-007`, `BUG-023`, `BUG-041`) never having its true cause found.

## Root cause

`_handler`'s only path is: log, then show a blocking modal, unconditionally.
There is no distinction between "the interactive GUI session is still alive
and a human can see and dismiss a dialog" and "there is no interactive session
(headless, or the window is already gone)". `QDialog.exec()` assumes the
former is always true.

## Fix — not implemented here, scope only

Two independent fixes, likely both warranted:

1. **`sys.excepthook` should never block indefinitely.** At minimum, detect a
   non-interactive session (`QT_QPA_PLATFORM=offscreen`, or no visible
   top-level window) and skip the modal — log only. Consider a timeout on the
   dialog itself regardless of platform, so a real interactive session can't
   hang forever either if the user simply never responds and something else
   depends on this returning (e.g. a watchdog).
2. **A supervising process-level timeout is not a fix, it is a mitigation.**
   `EPIC-009`'s `test_the_real_process_starts_and_stops_cleanly` (mode 9)
   catches this class going forward via `subprocess.run(..., timeout=...)`,
   but that only detects it in the Sanity tier — it does nothing for a real
   user.

## Regression test

`tests/sanity/test_self_check_process.py::test_the_real_process_starts_and_stops_cleanly`
already covers the *symptom* (process must exit within budget) for the
`--self-check` path specifically. Once this is root-caused and fixed, add a
regression test for the *mechanism*: an uncaught exception under
`QT_QPA_PLATFORM=offscreen` must not block process exit, asserted directly
against `_handler` rather than through a 30-second subprocess round-trip.


## Fix landed

`_install_exception_handler`'s `_handler` now checks
`is_headless_qt_platform()` (new shared helper,
`src/presentation/ui/common/qt_platform.py`) before constructing the dialog —
under a headless platform it logs and returns, never calling `dialog.exec()`.
A real interactive session is unaffected: the dialog still shows.

Verified by re-running the exact fault injection that found this bug:
`raise` inside `teardown()`, both before any step ran and after
`app_engine.stop()` completed. Both now produce a clean **exit code 1** in
under 5 seconds — previously both hung until an external 30s timeout killed
the process.

Fast regression test:
`tests/unit/presentation/ui/test_app_bootstrapper_exception_handler.py` — 3
tests, calls the installed `sys.excepthook` directly (no subprocess), proven
red-then-green: reverting the fix reproduces the original failure signature
(`dialog.exec()` called) in 1.7s, not a hang, because the test module patches
`CriticalErrorDialog` unconditionally for every test so a regression here can
never hang CI the way the original bug hung the real process. Restored and
re-verified green immediately after.

`tests/sanity/test_self_check_process.py` (the test that originally found
this) continues to cover the same class end-to-end, as a real subprocess.

Full gate re-run clean: 1,795 passed (+4 from the new regression test module),
only the two pre-existing, unrelated `BUG-046`/`BUG-047` remain.

## Not investigated

Whether this mechanism was the actual root cause of `BUG-007`/`023`/`041` (the
three previously "fixed" shutdown-hang bugs this bug's report named as
plausible candidates). Worth checking those three bugs' original repro steps
against this one before considering the connection closed either way.
