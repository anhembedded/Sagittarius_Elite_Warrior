"""`IAlertSettingsSource` that survives a restart (`BOT-191`).

One JSON file in the data root's state holds what the owner set: today each bot's mode, in the
shape `{"schema": "sew.alert-settings/1", "bot_modes": {"<bot id>": "critical_only"}}`. A new
setting is a new key with a default, so an older file stays readable.

**A missing or unreadable file is every default** (all bots `ON`), the safe side for an alert
system: more messages, never fewer. No file exists until the owner sets a mode; a file this
build cannot read (not JSON, another schema) is left alone and told once in the log, and is
moved aside to `<name>.unreadable` when the owner next saves, so a later build can still be
shown it. A single entry with a mode this build does not know is skipped and the rest kept,
so a file written by a newer build loses nothing it understands. The file holds bot ids and
modes only: no secret, no webhook.

Written by write-temp-then-rename, so a reader sees the old file or the new one. A read-only
copy of the app (a second instance) keeps the owner's change in memory and writes nothing.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_settings_source import (
    IAlertSettingsSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_bot_alert_modes import (
    IBotAlertModes,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)

logger = logging.getLogger("App.Alerting")

SETTINGS_SCHEMA = "sew.alert-settings/1"
_UNREADABLE_SUFFIX = ".unreadable"


class JsonAlertSettings(IAlertSettingsSource, IBotAlertModes):
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self._path = path
        self._read_only = read_only
        self._lock = threading.Lock()
        modes, self._unreadable = _read(path)
        self._modes: dict[str, BotAlertMode] = modes

    def current(self) -> AlertSettings:
        with self._lock:
            return AlertSettings(bot_modes=dict(self._modes))

    def modes(self) -> Mapping[str, BotAlertMode]:
        with self._lock:
            return dict(self._modes)

    def set_mode(self, bot_id: str, mode: BotAlertMode) -> None:
        with self._lock:
            updated = dict(self._modes)
            if mode is BotAlertMode.ON:
                updated.pop(bot_id, None)
            else:
                updated[bot_id] = mode
            if not self._read_only:
                self._write(updated)
            self._modes = updated
        logger.info(
            "Bot %s may tell: %s%s [alert-settings]",
            bot_id,
            mode.value,
            " (this copy is read-only: not kept)" if self._read_only else "",
        )

    def _write(self, modes: Mapping[str, BotAlertMode]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._unreadable and self._path.exists():
            self._path.replace(
                self._path.with_name(self._path.name + _UNREADABLE_SUFFIX)
            )
            self._unreadable = False
        document = {
            "schema": SETTINGS_SCHEMA,
            "bot_modes": {bot_id: mode.value for bot_id, mode in sorted(modes.items())},
        }
        temporary = self._path.with_name(self._path.name + ".tmp")
        temporary.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(temporary, self._path)


def _read(path: Path) -> tuple[dict[str, BotAlertMode], bool]:
    """The modes in the file, and whether the file exists but could not be read."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, False
    except (OSError, UnicodeDecodeError) as exc:
        return _defaults(path, f"it cannot be read ({type(exc).__name__})")
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        return _defaults(path, "it is not valid JSON")
    if (
        not isinstance(raw, dict)
        or raw.get("schema") != SETTINGS_SCHEMA
        or not isinstance(raw.get("bot_modes"), dict)
    ):
        return _defaults(path, "it is not a file of this schema")
    modes: dict[str, BotAlertMode] = {}
    skipped = 0
    for bot_id, value in raw["bot_modes"].items():
        try:
            modes[str(bot_id)] = BotAlertMode(value)
        except ValueError:
            skipped += 1
    if skipped:
        logger.warning(
            "%s: %d bot mode(s) are not ones this build knows and are ignored [alert-settings]",
            path.name,
            skipped,
        )
    return modes, False


def _defaults(path: Path, why: str) -> tuple[dict[str, BotAlertMode], bool]:
    logger.warning(
        "%s is not used, every bot may tell everything: %s; it is kept aside when you "
        "next set a bot's mode [alert-settings]",
        path.name,
        why,
    )
    return {}, True
