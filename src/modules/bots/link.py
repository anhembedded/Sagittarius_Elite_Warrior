"""`bots` on the remote link: its wire roots and the bridge's read of its files (`EPIC-047C`).

The second file of `modules/bots/` that `shell/` may import (`boundaries/zones.py`,
`is_module_entry_point`). It exists because `module.py` is the whole module: importing it loads
every handler, binding and adapter of `bots` and `trading`, about a second on the VPS, and the
bridge is started by `sshd` for each session. This file imports the wire roots and the store
reader and nothing else, so a bridge that imports only link files starts in a fraction of that.
It holds no behaviour of its own.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.store_bridge_bots import (
    StoreBridgeBots,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.result import (
    BotList,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.wire_roots import (
    BOTS_WIRE_ROOTS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    RefusedBotFile,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_bots import (
    IBridgeBots,
)


def wire_roots() -> tuple[WireRoot, ...]:
    """The types of this module's contracts that cross the remote link (`EPIC-047A`)."""
    return BOTS_WIRE_ROOTS


def decoded_bot_list(
    value: object,
) -> tuple[tuple[BotSnapshot, ...], tuple[RefusedBotFile, ...]] | None:
    """The bots and the refused files of a decoded `BotList`, or `None` when `value` is not one.

    The desktop reads the bridge's snapshot through this (`EPIC-047E`): `BotList` is an application
    result, which `shell/` may not import."""
    if not isinstance(value, BotList):
        return None
    return value.bots, value.refused


def bridge_bots(directory: Path) -> IBridgeBots:
    """The bots' files in `directory`, read-only, for the bridge."""
    return StoreBridgeBots(directory)
