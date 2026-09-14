"""How much room a contributed widget wants (HLD §4).

Three buckets, not pixels: the surface host owns the real geometry and the
user's saved perspective overrides any hint. A module that needs an exact size
is describing a widget, not a contribution.
"""

from __future__ import annotations

from enum import Enum


class SizeHint(Enum):
    #: A reading or a control strip — as little height as it can get.
    COMPACT = "compact"
    #: The default: a panel with content.
    REGULAR = "regular"
    #: Wants the full height of its dock area (a long list, a chart).
    TALL = "tall"
