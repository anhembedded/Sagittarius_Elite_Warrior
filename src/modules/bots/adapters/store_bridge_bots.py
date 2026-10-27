"""`EPIC-047C` — the bots' files as the remote link's bridge reads them: read-only, and nothing else.

The bridge is a second process beside the host, so it reads the store's files as `bot list` and
`bot show` do. It holds the store through `ReadOnlyBotStore`, which refuses a save and a delete by
construction, and it takes the host's own queries' handlers for what it shows (`ListBotsQueryHandler`,
`BotSnapshot.of`), so a bot looks on the desktop exactly as it looks in the Bots tab.

A file's **stamp** is what changes when the host writes it: the store replaces a file atomically
(a temporary file renamed over the old one), so the inode and the modification time change with
every write. One `scandir` reads no file; only a stamp that changed is followed by a read.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.handler import (
    ListBotsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.query import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.read_only_bot_store import (
    ReadOnlyBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BotId,
    InvalidBotIdError,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    BotReading,
    Wired,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_bots import (
    IBridgeBots,
)

BOT_SNAPSHOT_ROOT = "sew.bot-snapshot/1"
BOT_LIST_ROOT = "sew.bot-list/1"
_SUFFIX = ".json"
_READ_ONLY_REASON = "the remote link's bridge only reads the bots"


class StoreBridgeBots(IBridgeBots):
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._store = ReadOnlyBotStore(JsonBotStore(directory), _READ_ONLY_REASON)

    def stamps(self) -> Mapping[str, tuple[int, ...]]:
        stamps: dict[str, tuple[int, ...]] = {}
        try:
            with os.scandir(self._directory) as entries:
                for entry in entries:
                    stem = entry.name.removesuffix(_SUFFIX)
                    if stem == entry.name or not _is_bot_id(stem):
                        continue
                    try:
                        found = entry.stat()
                    except OSError:
                        continue  # replaced between the listing and the stat; the next look sees it
                    stamps[stem] = (found.st_mtime_ns, found.st_size, found.st_ino)
        except OSError:
            return {}
        return stamps

    def read(self, bot_id: str) -> BotReading:
        try:
            stored = self._store.load(BotId(bot_id))
        except (BotNotFoundError, InvalidBotIdError):
            return BotReading()
        except UnreadableBotError as unreadable:
            return BotReading(refused=unreadable.reason)
        except OSError as failure:
            return BotReading(
                refused=f"the file cannot be read ({type(failure).__name__})"
            )
        snapshot = BotSnapshot.of(stored.bot, bot_progress(stored))
        return BotReading(Wired(BOT_SNAPSHOT_ROOT, snapshot))

    def listing(self) -> Wired:
        return Wired(
            BOT_LIST_ROOT, ListBotsQueryHandler(self._store).execute(ListBotsQuery())
        )


def _is_bot_id(name: str) -> bool:
    try:
        BotId(name)
    except InvalidBotIdError:
        return False
    return True
