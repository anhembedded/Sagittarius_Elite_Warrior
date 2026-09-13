"""Where a contributed widget goes on a surface (HLD §4, ADR D22).

A `Place` is a **role in a layout**, not a widget class and not a coordinate: the
surface host decides that a `RAIL` entry becomes a right-hand `QDockWidget` and a
`STATUS_TILE` becomes a widget in the status bar. A module says what kind of
thing it is contributing; the shell says where that kind lives.

The list is canonical — `Docs/VOCABULARY/README.md` §2 defines each member, and
adding one is an HLD change, not a local decision.
"""

from __future__ import annotations

from enum import Enum


class Place(Enum):
    #: A whole navigable screen (the strangler period's legacy screens arrive here).
    SCREEN = "screen"
    #: The surface's own title area: identity, mode switches, system controls.
    HEADER = "header"
    #: The strip under the header: what the surface is currently pointed at.
    CONTEXT_BAR = "context_bar"
    #: The centre of the surface — its subject.
    WORKSPACE = "workspace"
    #: A side dock: lists, inspectors, checklists.
    RAIL = "rail"
    #: The bottom dock: logs, progress, anything append-only.
    CONSOLE = "console"
    #: A dialog the surface can raise.
    MODAL = "modal"
    #: One section of the Settings surface.
    SETTINGS_SECTION = "settings_section"
    #: One reading in the status bar.
    STATUS_TILE = "status_tile"
    #: A developer probe, only ever shown when developer mode is on.
    DEV_PROBE = "dev_probe"
