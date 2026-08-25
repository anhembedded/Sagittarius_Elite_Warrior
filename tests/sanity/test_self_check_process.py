"""
Sanity tier — OUT-of-process layer (`EPIC-009` D2/D2b's degenerate case).

`test_composition_root.py`'s IN-process tests import `build()`/`teardown()`
and call them inside pytest's own process. That is cheap and can inspect
Python objects directly, but it structurally cannot prove one thing: that the
real *process* — launched the way a user launches it, not imported the way a
test imports it — starts and stops cleanly. Inside pytest, `teardown()`
returning is not the same as the process dying, because pytest's own process
keeps running regardless; a surviving thread there is a proxy for the real
symptom, not the symptom itself.

This module launches `app_bootstrapper.py --self-check` with
`subprocess.run(...)`, exactly the way `python -m
Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper --self-check`
launches it for a human. `--self-check` runs the genuine `main()` — real
config, real DI container, real QApplication, real MainWindow, real Engine
shutdown — and changes exactly one thing: it schedules `app.quit()` on the
first event-loop turn instead of waiting for a window close. See
`app_bootstrapper.py`'s module docstring for what this is and is not (it is
not `EPIC-009` D2b's general control channel — no event is published, no
command is dispatched from outside the process; that protocol is still
`Proposed` and gated on open questions, several of them security-relevant for
an application holding exchange API credentials).

Three of the twelve failure modes in `EPIC-009`'s ADR are provable only here:

  mode  7  cannot enter    -> a non-zero exit code, or a timeout
  mode  9  cannot exit     -> a timeout (the process never returns)
  mode 10  exits dirty     -> a non-zero exit code, or diagnostic noise on
                              stderr

Mode 9 is not hypothetical here — it was reproduced while building this test:
`sys.excepthook` (`app_bootstrapper.py:249-269`) shows a blocking modal dialog
on any uncaught exception, unconditionally. Under `QT_QPA_PLATFORM=offscreen`
nothing can ever dismiss it, so the process hangs forever rather than exiting
non-zero — confirmed even when the exception fires *after* `app_engine.stop()`
has already completed cleanly, ruling out "a background thread survived" as
the cause. Filed as `BUG-048` (P1); the timeout below is this test's own
mitigation for that class, not evidence it cannot happen in production.

Modes 1-6, 11, 12 (the DI graph, routes, registries) are `test_composition_
root.py`'s job — cheaper there, and this module deliberately does not repeat
them.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

#: Real boot + real Engine/Qt teardown, observed at ~4.4s locally. Generous on
#: purpose — this budget asserts "the process terminates", not "it terminates
#: quickly"; a tight budget here would make the tier flaky on a loaded CI
#: runner for a question this test does not ask.
_PROCESS_BUDGET_SECONDS = 30

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Startup noise this platform/toolchain emits that carries no diagnostic
#: value — narrow on purpose, same contract as conftest.py's diagnostic_guard
#: allowlists: every entry here needs to earn its place, not accumulate one.
_ALLOWED_STDERR_SUBSTRINGS = (
    # Qt offscreen platform plugin limitation, not an application defect —
    # observed on every offscreen launch regardless of this app's own code.
    "This plugin does not support propagateSizeHints()",
)


def _run_self_check() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper",
            "--self-check",
        ],
        cwd=str(_REPO_ROOT.parent),
        capture_output=True,
        text=True,
        timeout=_PROCESS_BUDGET_SECONDS,
        check=False,
    )


def test_the_real_process_starts_and_stops_cleanly() -> None:
    """Modes 7, 9, 10 — the one thing no in-process test can prove.

    A hang here surfaces as `subprocess.TimeoutExpired`, a real pytest
    failure with a real traceback — not a hung CI job the way the retired
    sanity fixtures' bare `app.stop()` in teardown used to (see BUG-007,
    BUG-023, BUG-041, two of them P1, all three found by a human watching a
    real window fail to close).
    """
    started = time.monotonic()
    result = _run_self_check()
    elapsed = time.monotonic() - started

    assert result.returncode == 0, (
        f"--self-check exited {result.returncode} (mode 7 or 10) after "
        f"{elapsed:.1f}s.\n--- stdout ---\n{result.stdout}\n--- stderr ---\n"
        f"{result.stderr}"
    )
    assert elapsed < _PROCESS_BUDGET_SECONDS, (
        f"--self-check took {elapsed:.1f}s against a {_PROCESS_BUDGET_SECONDS}s "
        f"budget — process exited, but slower than the tier's own contract "
        f"allows (mode 9's neighbor: technically not hung, but the budget "
        f"exists so a real hang fails fast instead of at pytest's own timeout)."
    )


def test_the_real_process_reports_a_clean_boot_and_shutdown_sequence() -> None:
    """The log itself is evidence, not just the exit code — an exit code of 0
    from a process that silently swallowed an exception during shutdown would
    still look like success by the test above alone."""
    result = _run_self_check()
    combined = result.stdout + result.stderr

    assert "App booted successfully" in combined, (
        f"--self-check's own log never confirmed a successful boot:\n{combined}"
    )
    assert "App stopped." in combined, (
        f"--self-check's own log never confirmed the Engine finished "
        f"stopping — teardown() may have exited early:\n{combined}"
    )


def test_the_real_process_stderr_is_clean() -> None:
    """Mode 8/10's process-boundary form — the diagnostic channels
    `conftest.py`'s `diagnostic_guard` observes in-process (Qt messages,
    Python logging, warnings) do not exist as such once the app is a separate
    process; stderr is what is left to inspect, and it must stay just as
    narrow an allowlist as the in-process guard's."""
    result = _run_self_check()

    unexpected = [
        line
        for line in result.stderr.splitlines()
        if line.strip()
        and not any(allowed in line for allowed in _ALLOWED_STDERR_SUBSTRINGS)
    ]

    assert unexpected == [], (
        f"--self-check wrote {len(unexpected)} unexpected stderr line(s):\n  "
        + "\n  ".join(unexpected)
    )
