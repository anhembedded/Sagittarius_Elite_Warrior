"""Where a contributed widget goes on a surface (HLD §4, ADR D22).

A `Place` is a **role in a layout**, not a widget class and not a coordinate: the
surface host decides that a `RAIL` entry becomes a right-hand `QDockWidget` and a
`STATUS_TILE` becomes a widget in the status bar. A module says what kind of
thing it is contributing; the shell says where that kind lives.

The list is canonical — `Docs/VOCABULARY/README.md` §2 defines each member, and
adding one is an HLD change, not a local decision.

**`str` mixin, added for `EPIC-025F`'s Engine harvest (`Sagittarius_Engine`
`TASK-043` E1, 2026-09-19).** The Engine's own future contribution mechanism
must not hardcode which places exist — `TASK-043`'s own text: *"the engine does
not know which kinds exist — `kind` is an opaque string the app registers."*
This app's `Place` stays the closed, HLD-governed vocabulary above; only its
runtime *type* changes, from a bare `Enum` (opaque to everything, including
`str`) to `(str, Enum)` (an `Enum` value that also satisfies `isinstance(p,
str)`), which is exactly this codebase's own established pattern for a closed
set of string identities — see `support/binance_gateway/contracts/trading_venue.py`
and ~40 other contracts. Verified on this repo's own Python 3.12 that the mixin
changes nothing else: `str(Place.SCREEN)` still prints `"Place.SCREEN"` (Python's
`(str, Enum)` mixin does not adopt `StrEnum`'s different `__str__`), member
identity/hash/`==`-to-itself are unaffected, and every existing `Place.X`
call site keeps working unchanged — only `Place.X == "x"` and `isinstance(Place.X,
str)`, both previously `False`, become `True`. No call site in this codebase
relies on either being `False` (verified: no code compares a `Place` member
against a bare string, since nothing outside this file and its consumers had a
reason to).
"""

from __future__ import annotations

from enum import Enum


class Place(str, Enum):
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
