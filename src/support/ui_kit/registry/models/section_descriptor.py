"""`EPIC-016` — a sidebar section's own ordering, registry-internal (see
`nav_metadata.py`'s module docstring for why)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SectionDescriptor:
    """One sidebar section's title and sort weight.

    @details `sequence` decides section order (lower first); ties are broken
    by insertion order, matching `dict`'s own iteration guarantee — no
    separate tie-break field, since two sections sharing a weight and a
    title is not a case this app has.
    """

    key: str
    title: str
    sequence: int = 100
