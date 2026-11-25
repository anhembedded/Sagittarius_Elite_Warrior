"""`EPIC-047C` — what one bridge session reads and writes, as a value: the host's files and its control door."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_bot_log import (
    IBridgeBotLog,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_bots import (
    IBridgeBots,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_candles import (
    IBridgeCandles,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_facts import (
    IBridgeFacts,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_command_door import (
    ICommandDoor,
)


@dataclass(frozen=True, slots=True)
class SessionPorts:
    bots: IBridgeBots
    facts: IBridgeFacts
    door: ICommandDoor
    #: `EPIC-047H`: the host's other files by kind (`market`, `reads`), each watched like the facts file.
    documents: Mapping[str, IBridgeFacts] = field(default_factory=dict)
    #: `EPIC-047H`: the host's closed candles; `None` where the build offers none (the `candles` call says so).
    candles: IBridgeCandles | None = None
    #: `EPIC-047F`: a bot's own log lines; `None` where the build offers none (the `bot_log` call says so).
    bot_log: IBridgeBotLog | None = None
