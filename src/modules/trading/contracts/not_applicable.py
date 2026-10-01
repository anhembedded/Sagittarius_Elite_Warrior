"""`EPIC-028O` — the answer to a read the addressed venue has no figure for.

@details Spot has no leverage, no leverage brackets and no mark price. A
query for one of them on Spot answers `NotApplicable.ON_THIS_VENUE`, a named
value the desk can show as such, never an invented figure (a leverage of 1,
the last price as the mark) that a caller would size an order with. A union
`X | NotApplicable` makes every caller narrow it before using the figure.
"""

from __future__ import annotations

from enum import Enum


class NotApplicable(Enum):
    """The venue has no such figure."""

    ON_THIS_VENUE = "not_applicable_on_this_venue"
