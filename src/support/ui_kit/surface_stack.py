"""A view that shows one of several surfaces at a time (`EPIC-033I`).

The Trade mode trades one venue at a time, and each venue keeps its own
layout (HLD §11.2.1): a surface per venue, one shown, the others kept. The
mode's host (`ModeHost`) asks such a view which surfaces it has and which one
shows, so that:
- View lists the panels of the surface that shows, and follows it when the
  person chooses another;
- every surface's layout is remembered on exit and restored on start, each
  under its own surface id (the Engine's `PerspectiveStore`);
- Window → Reset layout puts the surface that shows back to its default;
  the others keep the layouts the person left them in.

A `Protocol`: the implementers are views, `QWidget`s, and Shiboken forbids a
second `QObject`-derived base and conflicts with `ABCMeta`
(`architecture-rule.md` §2.1, reason (a)).

Plausible extensions, each a local change: a Backtest that keeps a layout per
strategy (one more implementer); a surface added while the mode runs (the
host already asks on every call rather than keeping a copy).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from sagittarius_engine.extensions.pyside_mvc.runtime.region_host import RegionHost


@runtime_checkable
class ISurfaceStack(Protocol):
    """Several surfaces, one shown at a time, each with its own layout."""

    def surfaces(self) -> Sequence[RegionHost]:
        """Every surface the view holds, shown or not."""
        ...

    def shown_surface(self) -> RegionHost | None:
        """The surface that shows now; `None` while the view shows none."""
        ...
