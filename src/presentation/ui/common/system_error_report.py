"""
@brief `SystemErrorReport` — one normalised shape for "something failed and a
human should be able to see it".

@details Two unrelated engine events describe failures with different fields:
`UiActionFailedEvent` (a slot that raised, with `function_name` and a full
`traceback`) and `runtime.tasks.failed` (a background task that died, with
`task_id`/`task_name` and an `Exception` object). Screens should not each
learn both shapes — that is precisely the duplication `EPIC-008` exists to
remove — so `SystemErrorFeed` normalises them into this one type and every
display reads only this.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SystemErrorReport:
    """
    @brief A failure worth showing to the user, in display-ready form.

    @details `frozen` on purpose: this crosses a fan-out to several screens,
    and one screen must not be able to edit what the next one sees. Unlike the
    domain events in `src/domain/events/`, nothing forces this to inherit
    `BaseEvent` — it is a presentation-layer payload, never published on the
    bus — so it keeps immutability.
    """

    #: Where the failure came from, in words a reader recognises — a slot name
    #: or a background task name, not a class path.
    source: str

    #: One-line summary, already prefixed with what kind of failure it is.
    summary: str

    #: Full traceback when one is available, else the exception text. Kept
    #: separate from `summary` so a panel can show one line and still have the
    #: detail on hand — `BOT-061` cost a misdirected investigation precisely
    #: because only the short message survived.
    detail: str
