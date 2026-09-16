"""`SystemFailureLog` — the subscriber that makes a swallowed failure visible.

## The defect this exists to close (`BUG-126`)

`safe_ui_action` publishes `UiActionFailedEvent` with a full traceback whenever
a UI slot raises, and the engine's task manager publishes `TaskFailed` whenever
a background task dies. `EPIC-008` §1 called both **zero-subscriber** paths and
ranked the finding P1: a failure in either left no trace anywhere a user could
see.

`EPIC-008G` answered it with `SystemErrorFeed`, a Qt feed that normalised both
events and re-emitted them on a signal — written, unit-tested, and **never
constructed**. Nothing in `src/` or `scripts/` named it, so at runtime both
events still had zero subscribers; the epic's P1 finding had been true the
whole time, behind a green gate and a passing test file. `BUG-126` is that, and
[`CS-002`](../../Docs/CASE_STUDIES/CS-002_the_subscriber_nobody_built.md) is why
no check said so.

## Why this is not a feed

Three properties decide it, and each one is a reason the Qt feed was the wrong
shape for this job:

1. **One owner, at boot.** The composition root constructs this once, so no
   screen wires it and a second or third screen costs nothing. A feed is
   constructed *by a screen*, which is how the previous answer ended up
   constructed by none of them. `bug-fix-rule.md` §2 names "add the same wiring
   to every Presenter" as the tell of a hotfix.
2. **No Qt, so it also works headless.** `BaseFeed` wraps the bus in
   `QtEventBridge` because touching a Qt object off the main thread is
   `BUG-031`. A logger has no such constraint, so this subscribes directly —
   and the CLI entry point, which has no `QApplication` at all, gets the same
   visibility as the GUI.
3. **It reports somewhere that exists.** A feed's signal needs a display to
   connect to it, and this application has no app-wide one — every log panel
   belongs to a screen. The `"App."` logger is the sink that is always there:
   it is the file `--dev`/`--debug` write, the file a reporter pastes, and the
   file `ci-local.ps1`'s "Run Log Scan" step greps for `ERROR`.

A screen that later wants these failures on its own panel is still free to add
the feed back — `SystemErrorReport` and its two normalisers stay in
`system_error_report.py`, so that feed would be the subscription and the
signal, and nothing else. `base_feed.py`'s own rule is to promote a fact to a feed when the
second consumer appears, not before; there is not yet a first.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.shell.system_error_report import (
    SystemErrorReport,
    from_task_failed,
    from_ui_action_failed,
)
from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.runtime.tasks.events import TaskFailed

#: The greppable subsystem tag `logging-rule.md` §8 requires. One
#: `grep '\[system-failure\]'` isolates every swallowed failure in a pasted
#: session log, without the reader having to know which of the two events
#: produced it.
_TAG = "[system-failure]"


class SystemFailureLog:
    """Subscribes once to both failure events and writes each one to the app's
    own logger."""

    def __init__(self, event_bus: IEventBus, logger: ILogger) -> None:
        self._logger = logger
        event_bus.on(UiActionFailedEvent, self._on_ui_action_failed)
        event_bus.on(TaskFailed, self._on_task_failed)

    def _on_ui_action_failed(self, event: UiActionFailedEvent) -> None:
        self._report(from_ui_action_failed(event))

    def _on_task_failed(self, event: TaskFailed) -> None:
        self._report(from_task_failed(event))

    def _report(self, report: SystemErrorReport) -> None:
        """`ERROR`, not `CRITICAL`: an operation failed and the process is
        still sound (`logging-rule.md` §6).

        The detail goes on its own line rather than into `extra`. `StdLogger`'s
        formatter renders `%(message)s` only, so anything in `extra` reaches the
        file exclusively through a handler that reads it — and the traceback is
        the one field `BOT-061` proved a reader cannot do without.
        """
        self._logger.error(f"{_TAG} {report.summary}")
        if report.detail and report.detail != report.summary:
            self._logger.error(f"{_TAG} {report.source} detail:\n{report.detail}")
