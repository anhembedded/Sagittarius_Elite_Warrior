"""`IAlertSettingsSource` that survives a restart (`BOT-191`, `EPIC-036D6`, `EPIC-036D7`).

One JSON file in the data root's state holds what the owner set: each bot's mode, the quiet hours
and the routing matrix (the shape and how it is read are `settings_document.py`). One object
serves the hub's reads and the Options page's edits (`IBotAlertModes`, `IQuietHoursSetting`,
`IAlertRouting`).

**A missing or unreadable file is every default** (all bots `ON`, no quiet hours, no routes), the
safe side for an alert system: more messages, never fewer. No file exists until the owner sets
something; a file this build cannot read (not JSON, another schema) is left alone and told once in
the log, and is moved aside to `<name>.unreadable` when the owner next saves, so a later build can
still be shown it. The file holds bot ids, modes, times, zone names and channel ids only: no
secret, no webhook.

Written by write-temp-then-rename, so a reader sees the old file or the new one. A read-only copy
of the app (a second instance) refuses a change: its alerting never runs, so a choice kept there
would reach nothing and only look saved.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.settings_document import (
    SettingsDocument,
    document_dict,
    read_document,
    zone_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_routing import (
    IAlertRouting,
)
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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.quiet_hours import QuietHours

logger = logging.getLogger("App.Alerting")

_UNREADABLE_SUFFIX = ".unreadable"
_READ_ONLY = "this copy of the app is read-only: nothing was changed"


class JsonAlertSettings(
    IAlertSettingsSource, IBotAlertModes, IQuietHoursSetting, IAlertRouting
):
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self._path = path
        self._read_only = read_only
        self._lock = threading.Lock()
        self._document = read_document(path)

    @property
    def read_only(self) -> bool:
        return self._read_only

    def current(self) -> AlertSettings:
        with self._lock:
            document = self._document
        return AlertSettings(
            routes=document.routes,
            bot_modes=dict(document.modes),
            quiet_hours=_quiet_hours_of(document.quiet),
        )

    def modes(self) -> Mapping[str, BotAlertMode]:
        with self._lock:
            return dict(self._document.modes)

    def set_mode(self, bot_id: str, mode: BotAlertMode) -> None:
        self._refuse_if_read_only()
        with self._lock:
            updated = dict(self._document.modes)
            if mode is BotAlertMode.ON:
                updated.pop(bot_id, None)
            else:
                updated[bot_id] = mode
            self._commit(replace(self._document, modes=updated))
        logger.info("Bot %s may tell: %s [alert-settings]", bot_id, mode.value)

    def quiet_hours(self) -> QuietHoursChoice | None:
        with self._lock:
            return self._document.quiet

    def set_quiet_hours(self, choice: QuietHoursChoice | None) -> None:
        self._refuse_if_read_only()
        if choice is not None:
            # A name that is no zone is refused before anything is written.
            zone_of(choice.zone_key)
        with self._lock:
            self._commit(replace(self._document, quiet=choice))
        logger.info(
            "Quiet hours are %s [alert-settings]", "off" if choice is None else "set"
        )

    def routes(self) -> tuple[AlertRoute, ...]:
        with self._lock:
            return self._document.routes

    def set_route(
        self, group: AlertGroup, channel_id: str, loudness: Loudness | None
    ) -> None:
        self._refuse_if_read_only()
        with self._lock:
            kept = tuple(
                route
                for route in self._document.routes
                if (route.group, route.channel_id) != (group, channel_id)
            )
            if loudness is not None:
                kept = (*kept, AlertRoute(group, channel_id, loudness))
            self._commit(replace(self._document, routes=kept))
        logger.info(
            "Route %s on %s is %s [alert-settings]",
            group.value,
            channel_id,
            "default" if loudness is None else loudness.value,
        )

    def _refuse_if_read_only(self) -> None:
        if self._read_only:
            raise PermissionError(_READ_ONLY)

    def _commit(self, document: SettingsDocument) -> None:
        """Writes `document`, then makes it the one in memory: a write that fails changes
        nothing (the lock is held by the caller)."""
        self._write(document)
        self._document = replace(document, unreadable=False)

    def _write(self, document: SettingsDocument) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._document.unreadable and self._path.exists():
            self._path.replace(self._aside())
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(document_dict(document), indent=2, ensure_ascii=False)
                    + "\n"
                )
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


def _quiet_hours_of(choice: QuietHoursChoice | None) -> QuietHours | None:
    """The hub's view; never raises, because the hub asks for every alert, Critical included.
    A name that is no zone (a file edited by hand, a bug upstream) is off, not a failure."""
    if choice is None:
        return None
    try:
        return QuietHours(choice.start, choice.end, zone_of(choice.zone_key))
    except ValueError:
        return None
