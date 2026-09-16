"""The two normalisers in `shell/system_error_report.py` (`BUG-126`).

They used to live inside the Qt feed that `BUG-126` deleted, where
`test_system_error_feed.py` reached them through a `QObject`, a
`QtEventBridge` and a Qt signal — three mechanisms with nothing to do with the
question "does a failure event become a readable report". These tests are what
that file asserted about the *shape*, at the tier the shape actually lives at.

The normalisers also stopped probing with `getattr(event, "field", default)`
here. Both events are dataclasses whose fields are all required, so every
default was unreachable; the tests below read the same fields the production
code does, which means a field renamed in the engine breaks them at import
rather than turning a report into the word `unknown`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.shell.system_error_report import (
    from_task_failed,
    from_ui_action_failed,
)
from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.runtime.tasks.events import TaskFailed


def test_a_failed_ui_action_names_the_slot_and_keeps_the_traceback() -> None:
    report = from_ui_action_failed(
        UiActionFailedEvent(
            function_name="_on_start_clicked",
            exception_type="AttributeError",
            message="no attribute 'publish'",
            traceback="Traceback (most recent call last):\n  line one\n  line two",
        )
    )

    assert report.source == "_on_start_clicked"
    assert "AttributeError" in report.summary
    assert "no attribute 'publish'" in report.summary
    # The whole traceback, not its first line: `BOT-061` is the investigation
    # that cost, and the reason `detail` is a separate field at all.
    assert report.detail.count("\n") == 2


def test_a_failed_task_is_named_by_its_task_name() -> None:
    report = from_task_failed(
        TaskFailed(
            task_id="task-7",
            task_name="historical-sync",
            error=ValueError("candle grid drifted"),
        )
    )

    assert report.source == "historical-sync"
    assert "historical-sync" in report.summary
    assert "ValueError" in report.summary
    assert "candle grid drifted" in report.detail


def test_a_failed_task_report_carries_both_identifiers() -> None:
    """`task_name` is what a reader recognises; `task_id` is what every other
    `runtime.tasks.*` event for the same task carries, so a reader correlating
    this line with the rest of a session needs both. It is also why the
    normaliser needs no `task_id` fallback for an empty name: there is no dead
    end to fall back from."""
    report = from_task_failed(
        TaskFailed(task_id="task-7", task_name="", error=RuntimeError("boom"))
    )

    assert "task-7" in report.summary
