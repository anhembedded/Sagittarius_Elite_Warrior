# EPIC-009E — Fix BUG-048: uncaught exception after boot hangs the process

**Status:** 🔴 Not started
**Depends on:** `EPIC-009B` (found while building it; not part of it)

## What

`_install_exception_handler`'s `sys.excepthook` (`app_bootstrapper.py`)
calls `dialog.exec()` unconditionally on any uncaught exception. Under
`QT_QPA_PLATFORM=offscreen` nothing can dismiss it, so the process hangs
forever instead of exiting non-zero. Confirmed by fault injection in
`EPIC-009B`, not hypothetical — see `Tasks/bug_report/incomplete/
BUG-048_uncaught_exception_after_boot_hangs_the_process_via_blocking_modal.md`
for the full reproduction (two independent injections, both hung).

## Two candidate fixes named in the bug report, neither implemented

1. Detect a non-interactive session (`QT_QPA_PLATFORM=offscreen`, or no
   visible top-level window) and skip the modal — log only.
2. A timeout on the dialog itself regardless of platform, so even a real
   interactive session where the user never responds cannot hang
   something else that depends on this call returning.

## Why this is worth doing beyond closing one P1

This is a plausible undiagnosed root cause behind `BUG-007`/`023`/`041` —
three previously "fixed" shutdown-hang bugs whose actual trigger may
have been an unrelated exception hitting this same blocking modal, not
whatever each of those bugs' own fixes addressed. Worth checking those
three bugs' original repro steps against this mechanism before
considering this fix complete.

## Regression test

`tests/sanity/test_self_check_process.py::test_the_real_process_starts_and_stops_cleanly`
already proves the *symptom* end-to-end (real subprocess must exit within
budget). Add a second, fast regression test asserting on `_handler`
directly — an uncaught exception under `QT_QPA_PLATFORM=offscreen` must
not block — so the fix is proven without a 30-second subprocess
round-trip on every run.
