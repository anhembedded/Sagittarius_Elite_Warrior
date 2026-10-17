"""`EPIC-038J` - the poller's shutdown fence: no command is dispatched into a closing application.

`stop()` cancels the scheduler job, waits for a poll already running, and closes the poller, so a
poll that fires afterwards does nothing. The rule is a type-level promise in prose only unless a test
holds it (`architecture-rule.md` §7.3), so these two do.
"""

from __future__ import annotations

import threading
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.hosted_control_poller import (
    HostedControlPoller,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_processor import (
    HostCommandProcessor,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    ListInbox,
    MemoryAudit,
    MovableClock,
    ScriptedExecutor,
)


class _CountingProcessor(HostCommandProcessor):
    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        super().__init__(ListInbox(), MemoryAudit(), ScriptedExecutor(), MovableClock())
        self.polls = 0
        self._entered = entered
        self._release = release

    def poll(self) -> None:
        self.polls += 1
        self._entered.set()
        self._release.wait(timeout=5)


def _poller(
    tmp_path: Path,
) -> tuple[HostedControlPoller, _CountingProcessor, threading.Event, threading.Event]:
    entered, release = threading.Event(), threading.Event()
    processor = _CountingProcessor(entered, release)
    return (
        HostedControlPoller(processor, tmp_path / "control"),
        processor,
        entered,
        release,
    )


def test_a_poll_after_stop_dispatches_nothing(tmp_path: Path) -> None:
    poller, processor, _, release = _poller(tmp_path)
    release.set()

    poller.stop(None)  # type: ignore[arg-type] - stop() reads nothing from the context
    poller.poll_once()

    assert processor.polls == 0


def test_stop_waits_for_a_poll_that_is_already_running(tmp_path: Path) -> None:
    poller, processor, entered, release = _poller(tmp_path)
    running = threading.Thread(target=poller.poll_once)
    running.start()
    assert entered.wait(timeout=5)
    stopped = threading.Event()

    stopper = threading.Thread(
        target=lambda: (poller.stop(None), stopped.set())  # type: ignore[arg-type]
    )
    stopper.start()

    assert not stopped.wait(timeout=0.2), (
        "stop() returned while a poll was still running"
    )
    release.set()
    running.join(timeout=5)
    stopper.join(timeout=5)
    assert stopped.is_set()
    poller.poll_once()
    assert processor.polls == 1
