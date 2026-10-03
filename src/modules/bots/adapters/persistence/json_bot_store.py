"""`EPIC-029B` — `IBotStore` on disk: one JSON file per bot (ADR D4).

`<directory>/<bot_id>.json`, written atomically by the only precedent this
repository has (`json_symbol_catalog_repository.py`): write a temporary file in
the same directory, flush it to disk, then `Path.replace()` it over the old one.
`replace` is atomic on one filesystem, so a crash before it leaves the previous
file whole, and a crash after it leaves the new one; never half of either.

Writes to one bot are serialised by a lock per bot id. The executor
(`EPIC-029E`) is the only runtime writer of a running bot, but a use case and
the executor can still meet on the same file — a stop request arriving while
the actor saves a fill — and the lock keeps the two whole.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.bot_record_codec import (
    BotRecordError,
    decode,
    encode,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    BotStoreReading,
    IBotStore,
    RefusedBotFile,
    StoredBot,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId

logger = logging.getLogger("App.Bots.Store")

_SUFFIX = ".json"
_TEMP_SUFFIX = ".json.tmp"


class JsonBotStore(IBotStore):
    """Bots as `<directory>/<bot_id>.json`."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def save(self, stored: StoredBot) -> None:
        bot_id = stored.bot.bot_id
        text = json.dumps(encode(stored), indent=2, sort_keys=True)
        with self._lock_for(bot_id):
            self._directory.mkdir(parents=True, exist_ok=True)
            temp_path = self._path(bot_id).with_suffix(_TEMP_SUFFIX)
            try:
                with temp_path.open("w", encoding="utf-8") as handle:
                    handle.write(text)
                    handle.flush()
                    os.fsync(handle.fileno())
                temp_path.replace(self._path(bot_id))
            finally:
                temp_path.unlink(missing_ok=True)
        logger.debug("Saved bot %s (%s)", bot_id, stored.bot.state.value)

    def load(self, bot_id: BotId) -> StoredBot:
        path = self._path(bot_id)
        if not path.is_file():
            raise BotNotFoundError(bot_id)
        return self._read(path)

    def load_all(self) -> BotStoreReading:
        if not self._directory.is_dir():
            return BotStoreReading()
        bots: list[StoredBot] = []
        refused: list[RefusedBotFile] = []
        for path in sorted(self._directory.glob(f"*{_SUFFIX}")):
            try:
                bots.append(self._read(path))
            except UnreadableBotError as exc:
                logger.debug("Refused bot file %s: %s", exc.name, exc.reason)
                refused.append(RefusedBotFile(exc.name, exc.reason))
        return BotStoreReading(tuple(bots), tuple(refused))

    def delete(self, bot_id: BotId) -> None:
        with self._lock_for(bot_id):
            path = self._path(bot_id)
            if not path.is_file():
                raise BotNotFoundError(bot_id)
            path.unlink()
        logger.info("Deleted bot %s", bot_id)

    def exists(self, bot_id: BotId) -> bool:
        return self._path(bot_id).is_file()

    def _read(self, path: Path) -> StoredBot:
        try:
            stored = decode(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, BotRecordError) as exc:
            raise UnreadableBotError(path.name, str(exc)) from exc
        if f"{stored.bot.bot_id.value}{_SUFFIX}" != path.name:
            raise UnreadableBotError(path.name, "the file name is not its bot id")
        return stored

    def _path(self, bot_id: BotId) -> Path:
        return self._directory / f"{bot_id.value}{_SUFFIX}"

    def _lock_for(self, bot_id: BotId) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(bot_id.value, threading.Lock())
