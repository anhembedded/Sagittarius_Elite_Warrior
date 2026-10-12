"""The task-failure normaliser in `shell/system_error_report.py` (`BUG-126`).

`from_ui_action_failed` moved to `shell/ui_action_failure.py` with its
subscriber (`EPIC-038A`); its test moved with it, to
`tests/unit/shell/test_ui_action_failure.py`.

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

from Sagittarius_Elite_Warrior.src.shell.system_error_report import from_task_failed
from sagittarius_engine.runtime.tasks.events import TaskFailed


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
