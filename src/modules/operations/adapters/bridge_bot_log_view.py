"""`EPIC-047F` — the host's bot-log files as the bridge's port: `IBotLogReader`'s page in the wire layer's own words."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_bot_log_reader import (
    IBotLogReader,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_bot_log import (
    BridgeLogLine,
    BridgeLogPage,
    IBridgeBotLog,
)


class BridgeBotLogView(IBridgeBotLog):
    def __init__(self, reader: IBotLogReader) -> None:
        self._reader = reader

    def read(self, bot_id: str, since: int) -> BridgeLogPage:
        page = self._reader.read(bot_id, since)
        return BridgeLogPage(
            tuple(BridgeLogLine(r.seq, r.at, r.level, r.text) for r in page.records),
            page.next_since,
        )
