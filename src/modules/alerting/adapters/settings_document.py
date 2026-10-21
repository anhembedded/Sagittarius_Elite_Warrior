"""The alert settings file as a value: what it holds, how it is read and how it is written
(`BOT-191`, `EPIC-036D6`, `EPIC-036D7`, `EPIC-036D8`).

Split from `JsonAlertSettings`, which keeps the lock, the commit and the ports. The file is
`{"schema": "sew.alert-settings/1", "bot_modes": {...}, "quiet_hours": {...}, "routes": [...],
"disabled_channels": [...]}`;
every key but `schema` and `bot_modes` is optional, so an older file stays readable, and every
entry this build cannot read is skipped, told once, with the rest kept (the safe side for an
alert system is more messages, never fewer).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import time, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_quiet_hours_setting import (
    SYSTEM_ZONE,
    QuietHoursChoice,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness

logger = logging.getLogger("App.Alerting")

SETTINGS_SCHEMA = "sew.alert-settings/1"


@dataclass(frozen=True)
class SettingsDocument:
    """What the file said, and whether it existed but was unusable."""

    modes: dict[str, BotAlertMode] = field(default_factory=dict)
    quiet: QuietHoursChoice | None = None
    routes: tuple[AlertRoute, ...] = ()
    disabled: frozenset[str] = frozenset()
    unreadable: bool = False


def document_dict(document: SettingsDocument) -> dict[str, Any]:
    """The JSON object a document is written as."""
    out: dict[str, Any] = {
        "schema": SETTINGS_SCHEMA,
        "bot_modes": {
            bot_id: mode.value for bot_id, mode in sorted(document.modes.items())
        },
    }
    quiet = document.quiet
    if quiet is not None:
        out["quiet_hours"] = {
            "start": quiet.start.strftime("%H:%M"),
            "end": quiet.end.strftime("%H:%M"),
            "zone": quiet.zone_key,
        }
    if document.routes:
        out["routes"] = [
            {
                "group": route.group.value,
                "channel": route.channel_id,
                "loudness": route.loudness.value,
            }
            for route in sorted(
                document.routes, key=lambda r: (r.group.value, r.channel_id)
            )
        ]
    if document.disabled:
        out["disabled_channels"] = sorted(document.disabled)
    return out


def read_document(path: Path) -> SettingsDocument:
    """What the file holds; the defaults, told once, when it cannot be used."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return SettingsDocument()
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
    return SettingsDocument(
        _modes_in(path, raw["bot_modes"]),
        _quiet_choice_in(path, raw.get("quiet_hours")),
        _routes_in(path, raw.get("routes")),
        _disabled_in(path, raw.get("disabled_channels")),
    )


def _modes_in(path: Path, raw: dict[str, Any]) -> dict[str, BotAlertMode]:
    modes: dict[str, BotAlertMode] = {}
    skipped = 0
    for bot_id, value in raw.items():
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
    return modes


def _routes_in(path: Path, raw: object) -> tuple[AlertRoute, ...]:
    """The routes the file names. An entry of a shape, group or loudness this build does not know
    is skipped, and so is a cell named twice (the file says two things, so the cell is its
    default again, never the last word of a hand edit); told once, the rest kept."""
    if raw is None:
        return ()
    entries = raw if isinstance(raw, list) else []
    found = [_route_in(entry) for entry in entries]
    cells = [(r.group, r.channel_id) for r in found if r is not None]
    repeated = {cell for cell in cells if cells.count(cell) > 1}
    kept = tuple(
        r for r in found if r is not None and (r.group, r.channel_id) not in repeated
    )
    skipped = (0 if isinstance(raw, list) else 1) + len(found) - len(kept)
    if skipped:
        logger.warning(
            "%s: %d route(s) are not ones this build knows and are ignored [alert-settings]",
            path.name,
            skipped,
        )
    return kept


def _disabled_in(path: Path, raw: object) -> frozenset[str]:
    """The channels switched off. An entry that is not a text is skipped, told once; a channel
    that stays on is the safe side for an alert system."""
    if raw is None:
        return frozenset()
    entries = raw if isinstance(raw, list) else []
    kept = frozenset(entry for entry in entries if isinstance(entry, str))
    skipped = (0 if isinstance(raw, list) else 1) + len(entries) - len(kept)
    if skipped:
        logger.warning(
            "%s: %d disabled channel entr(ies) are not ones this build knows and are ignored "
            "[alert-settings]",
            path.name,
            skipped,
        )
    return kept


def _route_in(entry: object) -> AlertRoute | None:
    """One route entry, or `None` for one of a shape or a name this build does not know."""
    if not isinstance(entry, dict) or not isinstance(entry.get("channel"), str):
        return None
    try:
        return AlertRoute(
            AlertGroup(entry["group"]), entry["channel"], Loudness(entry["loudness"])
        )
    except (KeyError, ValueError, TypeError):
        return None


def _quiet_choice_in(path: Path, raw: object) -> QuietHoursChoice | None:
    """The `quiet_hours` entry, or `None` for none or one this build cannot read (told once:
    quiet hours are the safe side off, so a bad entry never holds an alert back)."""
    if raw is None:
        return None
    try:
        return _parse_quiet(raw)
    except (KeyError, ValueError, TypeError):
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
    zone_of(choice.zone_key)
    return choice


def zone_of(zone_key: str) -> tzinfo | None:
    """The zone a name stands for; `None` is the machine's clock. Raises `ValueError` for a name
    that is no zone."""
    if zone_key == SYSTEM_ZONE:
        return None
    try:
        return ZoneInfo(zone_key)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"not a time zone: {zone_key!r}") from exc


def _without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """`json.loads` keeps the last of two equal keys; a file that does that was hand-edited and
    says two things, so it is not trusted."""
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("a member is named twice")
    return dict(pairs)


def _defaults(path: Path, why: str) -> SettingsDocument:
    logger.warning(
        "%s is not used, every bot may tell everything: %s; it is kept aside when you "
        "next set a bot's mode [alert-settings]",
        path.name,
        why,
    )
    return SettingsDocument(unreadable=True)
