"""`SystemErrorReport` — one normalised shape for "something failed and a human
should be able to see it", plus the two normalisers that produce it.

Two unrelated engine events describe failures with different fields:
`UiActionFailedEvent` (a slot that raised, with `function_name` and a full
`traceback`) and `TaskFailed` (a background task that died, with
`task_id`/`task_name` and an `Exception` object). Nothing downstream should
have to learn both shapes — that is the duplication `EPIC-008` exists to
remove — so they are normalised here, once, and every sink reads only this
type.

## Why the shell, and not `core/contracts/`

It began in `presentation/ui/common/`, beside the Qt feed that was the only
thing normalising these events. `BUG-126` is what moved it: that feed was never
constructed, so both failure paths reached nobody, and the fix is a subscriber
in the shell — which may not import the legacy tree
(`tests/unit/architecture/boundaries/rules.py`).

`core/contracts/` was the first attempt and was wrong twice over. It is a
**Qt-free** zone, and `UiActionFailedEvent` lives under the engine's
`pyside_mvc` extension, so `test_module_domain_is_qt_free.py` refused the
import — correctly, since importing it pulls the whole Qt extension into a zone
every other may import. Hiding that behind `if TYPE_CHECKING:` would have
satisfied the guard and answered nothing: with the feed deleted there is
exactly **one** consumer, the sink next door, so a shape placed where several
zones could reach it would be generality bought for nobody. That is the same
mistake at one level up from the bug itself — `base_feed.py`'s rule is to
promote a fact when the second consumer appears, and `BUG-126` is what it cost
to promote before the first one did.

If a screen later wants these failures on its own panel, the feed it writes
will need this type from a zone `support/` can import, and moving the file then
is two lines with a real consumer to justify it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.runtime.tasks.events import TaskFailed


@dataclass(frozen=True)
class SystemErrorReport:
    """A failure worth showing to the user, in display-ready form.

    `frozen` on purpose: this crosses a fan-out to several sinks, and one sink
    must not be able to edit what the next one sees. Unlike the domain events
    in `src/domain/events/`, nothing forces this to inherit `BaseEvent` — it is
    a report *about* an event, never published on the bus — so it keeps
    immutability.
    """

    #: Where the failure came from, in words a reader recognises — a slot name
    #: or a background task name, not a class path.
    source: str

    #: One-line summary, already prefixed with what kind of failure it is.
    summary: str

    #: Full traceback when one is available, else the exception text. Kept
    #: separate from `summary` so a sink can show one line and still have the
    #: detail on hand — `BOT-061` cost a misdirected investigation precisely
    #: because only the short message survived.
    detail: str


def from_ui_action_failed(event: UiActionFailedEvent) -> SystemErrorReport:
    """A UI slot raised and `safe_ui_action` caught it.

    Reads the event's fields by name rather than by `getattr` probing. The
    version of this code that `BUG-126` replaced probed every field with a
    default — `getattr(event, "function_name", "unknown slot")` — against a
    frozen dataclass whose fields are all required, so the defaults could never
    fire and the type checker could never help. `architecture-rule.md` §2.1
    calls that shape out by name.
    """
    return SystemErrorReport(
        source=event.function_name,
        summary=(
            f"UI error in {event.function_name}: "
            f"{event.exception_type}: {event.message}"
        ),
        detail=event.traceback,
    )


def from_task_failed(event: TaskFailed) -> SystemErrorReport:
    """A background task died.

    The summary carries **both** identifiers, and that is not belt-and-braces:
    `task_name` is what a reader recognises, while `task_id` is what the other
    `runtime.tasks.*` events for the same task carry, so a reader correlating
    this line with the rest of a session needs it. Naming both also removes the
    one question a fallback would have existed to answer — an empty `task_name`
    degrades the line rather than leaving a dead end — so there is no branch
    here, and no unreachable defensive code of the kind this commit deleted
    from the `getattr` probing above.
    """
    return SystemErrorReport(
        source=event.task_name,
        summary=(
            f"Background task '{event.task_name}' (id {event.task_id}) failed: "
            f"{type(event.error).__name__}: {event.error}"
        ),
        detail=str(event.error),
    )
