"""`market_data` on the remote link: its wire root and the bridge's read of the host's candle store (`EPIC-047H`).

The third file of this kind (`modules/bots/link.py`, `modules/operations/link.py`; `boundaries/zones.py`,
`is_module_entry_point`). It exists because `module.py` is the whole module: importing it loads SQLAlchemy and
every adapter, and the bridge is started by `sshd` for each session. This file imports the candle window type
and the read-only reader (plain `sqlite3`) and nothing else. It holds no behaviour of its own, and the bridge
that imports it can open a shard `mode=ro` and cannot create one.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.bridge_candles import (
    StoreBridgeCandles,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.composition.wire_roots import (
    MARKET_DATA_WIRE_ROOTS,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_candles import (
    IBridgeCandles,
)


def wire_roots() -> tuple[WireRoot, ...]:
    """The types of this module's contracts that cross the remote link."""
    return MARKET_DATA_WIRE_ROOTS


def bridge_candles(directory: Path) -> IBridgeCandles:
    """The host's candle store under `directory` (`<data root>/database`), read-only, for the bridge."""
    return StoreBridgeCandles(directory)
