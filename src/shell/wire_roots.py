"""`EPIC-047A` — the closed list of types the remote link carries, as the codec's registry.

Each module declares the roots of its own contracts in its `link.py` (`EPIC-047C` moved them from
`module.py`, which loads the whole module); the shell is where they meet, because only the shell
may import every module's entry points. Adding a type to the link is one entry in a module's list
and one contract test (`tests/unit/support/wire/contract/`); the guard fails on an entry without its test.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.link import (
    wire_roots as bots_wire_roots,
)
from Sagittarius_Elite_Warrior.src.modules.operations.link import (
    wire_roots as operations_wire_roots,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots


def link_roots() -> WireRoots:
    """The registry of every type this build carries, refusing at once a graph it cannot carry."""
    return WireRoots((*bots_wire_roots(), *operations_wire_roots()))
