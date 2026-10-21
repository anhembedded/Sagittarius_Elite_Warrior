"""`IAlertSettingsSource` that survives a restart (`BOT-191`, `EPIC-036D6`).

One JSON file in the data root's state holds what the owner set: each bot's mode and the quiet
hours, in the shape `{"schema": "sew.alert-settings/1", "bot_modes": {"<bot id>": "critical_only"},
"quiet_hours": {"start": "22:00", "end": "07:00", "zone": "Europe/Berlin"}}`. A new setting is a
new key with a default, so an older file stays readable; a `quiet_hours` entry this build cannot
read is ignored, told once, and the rest kept.

**A missing or unreadable file is every default** (all bots `ON`), the safe side for an alert
system: more messages, never fewer. No file exists until the owner sets a mode; a file this
build cannot read (not JSON, another schema) is left alone and told once in the log, and is
moved aside to `<name>.unreadable` when the owner next saves, so a later build can still be
shown it. A single entry with a mode this build does not know is skipped and the rest kept,
so a file written by a newer build loses nothing it understands. The file holds bot ids and
modes only: no secret, no webhook.

Written by write-temp-then-rename, so a reader sees the old file or the new one. A read-only
copy of the app (a second instance) refuses a change: its alerting never runs, so a choice kept
there would reach nothing and only look saved.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_settings_source import (
    IAlertSettingsSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_bot_alert_modes import (
    IBotAlertModes,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_quiet_hours_setting import (
    IQuietHoursSetting,
    QuietHoursChoice,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.quiet_hours import QuietHours

logger = logging.getLogger("App.Alerting")

SETTINGS_SCHEMA = "sew.alert-settings/1"
_UNREADABLE_SUFFIX = ".unreadable"


@dataclass(frozen=True)
class _Document:
    """What the file said: the modes, the quiet hours, and whether it existed but was unusable."""

    modes: dict[str, BotAlertMode] = field(default_factory=dict)
    quiet: QuietHoursChoice | None = None
    unreadable: bool = False


class JsonAlertSettings(IAlertSettingsSource, IBotAlertModes, IQuietHoursSetting):
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self._path = path
        self._read_only = read_only
        self._lock = threading.Lock()
        document = _read(path)
        self._unreadable = document.unreadable
        self._modes: dict[str, BotAlertMode] = document.modes
        self._quiet: QuietHoursChoice | None = document.quiet

    @property
    def read_only(self) -> bool:
        return self._read_only

    def current(self) -> AlertSettings:
        with self._lock:
            return AlertSettings(
                bot_modes=dict(self._modes), quiet_hours=_quiet_hours_of(self._quiet)
            )

    def modes(self) -> Mapping[str, BotAlertMode]:
        with self._lock:
            return dict(self._modes)

    def set_mode(self, bot_id: str, mode: BotAlertMode) -> None:
        if self._read_only:
            raise PermissionError(
                "this copy of the app is read-only: nothing was changed"
            )
        with self._lock:
            updated = dict(self._modes)
            if mode is BotAlertMode.ON:
                updated.pop(bot_id, None)
            else:
                updated[bot_id] = mode
            self._write(updated, self._quiet)
            self._modes = updated
        logger.info("Bot %s may tell: %s [alert-settings]", bot_id, mode.value)

    def quiet_hours(self) -> QuietHoursChoice | None:
        with self._lock:
            return self._quiet

    def set_quiet_hours(self, choice: QuietHoursChoice | None) -> None:
        if self._read_only:
            raise PermissionError(
                "this copy of the app is read-only: nothing was changed"
            )
        with self._lock:
            self._write(self._modes, choice)
            self._quiet = choice
        logger.info(
            "Quiet hours are %s [alert-settings]", "off" if choice is None else "set"
        )

    def _write(
        self, modes: Mapping[str, BotAlertMode], quiet: QuietHoursChoice | None
    ) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._unreadable and self._path.exists():
            self._path.replace(self._aside())
            self._unreadable = False
        document = {
            "schema": SETTINGS_SCHEMA,
            "bot_modes": {bot_id: mode.value for bot_id, mode in sorted(modes.items())},
        }
        if quiet is not None:
            document["quiet_hours"] = {
                "start": quiet.start.strftime("%H:%M"),
                "end": quiet.end.strftime("%H:%M"),
                "zone": quiet.zone_key,
            }
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        finally:
            temporary.unlink(missing_ok=True)

    def _aside(self) -> Path:
        """Where an unreadable file goes: never over an earlier one kept the same way."""
        candidate = self._path.with_name(self._path.name + _UNREADABLE_SUFFIX)
        number = 1
        while candidate.exists():
            number += 1
            candidate = self._path.with_name(
                f"{self._path.name}{_UNREADABLE_SUFFIX}.{number}"
            )
        return candidate


def _read(path: Path) -> _Document:
    """What the file holds, and whether it exists but could not be read."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _Document()
    except (OSError, UnicodeDecodeError) as exc:
        return _defaults(path, f"it cannot be read ({type(exc).__name__})")
    try:
        raw: Any = json.loads(text, object_pairs_hook=_without_duplicates)
    except (ValueError, RecursionError):
        return _defaults(path, "it is not valid JSON, or names a member twice")
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
        except (ValueError, TypeError):
            skipped += 1
    if skipped:
        logger.warning(
            "%s: %d bot mode(s) are not ones this build knows and are ignored [alert-settings]",
            path.name,
            skipped,
        )
    return _Document(modes, _quiet_choice_in(path, raw.get("quiet_hours")))


def _quiet_choice_in(path: Path, raw: object) -> QuietHoursChoice | None:
    """The `quiet_hours` entry, or `None` for none or one this build cannot read (told once:
    quiet hours are the safe side off, so a bad entry never holds an alert back)."""
    if raw is None:
        return None
    try:
        return _parse_quiet(raw)
    except (KeyError, ValueError, TypeError, ZoneInfoNotFoundError):
        logger.warning(
            "%s: the quiet hours are not ones this build can read and are ignored "
            "[alert-settings]",
            path.name,
        )
        return None


def _parse_quiet(raw: object) -> QuietHoursChoice:
    if not isinstance(raw, dict):
        raise TypeError("quiet_hours is not an object")
    choice = QuietHoursChoice(
        time.fromisoformat(str(raw["start"])),
        time.fromisoformat(str(raw["end"])),
        str(raw["zone"]),
    )
    ZoneInfo(choice.zone_key)
    return choice


def _quiet_hours_of(choice: QuietHoursChoice | None) -> QuietHours | None:
    if choice is None:
        return None
    return QuietHours(choice.start, choice.end, ZoneInfo(choice.zone_key))


def _without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """`json.loads` keeps the last of two equal keys; a file that does that was hand-edited and
    says two things, so it is not trusted."""
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("a member is named twice")
    return dict(pairs)


def _defaults(path: Path, why: str) -> _Document:
    logger.warning(
        "%s is not used, every bot may tell everything: %s; it is kept aside when you "
        "next set a bot's mode [alert-settings]",
        path.name,
        why,
    )
    return _Document(unreadable=True)
