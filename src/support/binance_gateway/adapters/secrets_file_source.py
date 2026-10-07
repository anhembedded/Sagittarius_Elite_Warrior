"""`EPIC-021B` — reads/writes `secrets.local.json`, the gitignored fallback
for exchange credentials. `BUG-176` — one entry per venue."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Credentials")

_API_KEY_FIELD = "API_KEY"
_API_SECRET_FIELD = "API_SECRET"  # noqa: S105 - JSON field name, not a secret value
_VENUES_FIELD = "venues"

#: The venues the file served before `BUG-176`, when it held one pair at its top
#: level that both of them read. A top-level pair is still read for these two until
#: the file is next changed, when it is copied into an entry of each and removed, so
#: no later change to one venue's key can reach the other's.
_LEGACY_VENUES = (TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET)


class SecretsFileSource:
    """@brief Read/write access to one local, gitignored JSON file holding an
    `API_KEY`/`API_SECRET` pair for each venue it has a key for.

    @details Same failure contract as `sagittarius_engine`'s `JsonSource`: a
    missing or malformed file reads as "nothing configured", never raises —
    a corrupt secrets file must degrade credential resolution to `NONE`, not
    crash the app. Changing one venue's entry leaves every other venue's as it
    was (`BUG-176`: a key pasted for one venue replaced the working key of
    another).
    """

    def __init__(self, filepath: str) -> None:
        self._filepath = filepath

    def read(self, venue: TradingVenue) -> tuple[str, str] | None:
        """@return `(api_key, api_secret)` of `venue` if the file exists, parses,
        and both fields are non-empty; `None` otherwise."""
        data = self._load()
        if data is None:
            return None
        return _pair(_entries(data).get(venue.value)) or _legacy_pair(data, venue)

    def write(self, venue: TradingVenue, api_key: str, api_secret: str) -> None:
        """@brief Replaces `venue`'s pair, and nothing else in the file.
        @details `BUG-097` — chmod'd to owner-only (`0o600`) right after
        writing: `open(..., "w")` alone leaves the file at the process
        umask's default, typically world-readable, so any other local
        user on a shared machine (a VPS, exactly this repo's own deploy
        target per `README.md`) could read the key/secret straight off
        disk. `.gitignore` already keeps it out of the repo (`EPIC-021B`)
        — file-system exposure is the same category of leak, just not the
        one that epic checked for. A no-op on Windows (permission bits
        don't map the same way there), never raises either way.
        """
        _require_testnet(venue)
        data = _without_legacy_pair(self._load_for_change())
        _entries(data)[venue.value] = {
            _API_KEY_FIELD: api_key,
            _API_SECRET_FIELD: api_secret,
        }
        self._save(data)

    def remove(self, venue: TradingVenue) -> None:
        """Deletes `venue`'s pair; every other venue's stays. A venue with no
        pair is left as it is."""
        _require_testnet(venue)
        if not os.path.exists(self._filepath):
            return
        data = _without_legacy_pair(self._load_for_change())
        _entries(data).pop(venue.value, None)
        self._save(data)

    def _load(self) -> dict[str, Any] | None:
        if not os.path.exists(self._filepath):
            return None
        try:
            with open(self._filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Could not read %s: %s. Treating credentials as not configured.",
                self._filepath,
                exc,
            )
            return None
        return data if isinstance(data, dict) else None

    def _load_for_change(self) -> dict[str, Any]:
        """The file's content to change. A file that exists but cannot be read
        as a JSON object is moved to `<file>.corrupt` first, never overwritten:
        rewriting it from nothing would destroy every other venue's key in it."""
        data = self._load()
        if data is not None:
            return data
        if os.path.exists(self._filepath):
            backup = f"{self._filepath}.corrupt"
            os.replace(self._filepath, backup)
            logger.warning(
                "%s could not be read; kept as %s and started afresh.",
                self._filepath,
                backup,
            )
        return {}

    def _save(self, data: dict[str, Any]) -> None:
        """Writes to a temporary file in the same directory and swaps it in, so a
        crash mid-write leaves the old file whole."""
        directory = os.path.dirname(self._filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)
        temporary = f"{self._filepath}.tmp"
        with open(temporary, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        try:
            os.chmod(temporary, 0o600)
        except OSError as exc:
            logger.warning(
                "Could not set owner-only permissions on %s: %s",
                self._filepath,
                exc,
            )
        os.replace(temporary, self._filepath)


def _require_testnet(venue: TradingVenue) -> None:
    """A real-money secret never reaches this file (`EPIC-034` D10)."""
    if venue.is_mainnet:
        raise ValueError(f"{venue.name} keys are kept in the keyring, never in a file")


def _entries(data: dict[str, Any]) -> dict[str, Any]:
    """The per-venue entries of `data`, created in place when absent."""
    entries = data.get(_VENUES_FIELD)
    if not isinstance(entries, dict):
        entries = {}
        data[_VENUES_FIELD] = entries
    return entries


def _pair(entry: object) -> tuple[str, str] | None:
    if not isinstance(entry, dict):
        return None
    api_key = entry.get(_API_KEY_FIELD)
    api_secret = entry.get(_API_SECRET_FIELD)
    if not api_key or not api_secret:
        return None
    return api_key, api_secret


def _legacy_pair(data: dict[str, Any], venue: TradingVenue) -> tuple[str, str] | None:
    return _pair(data) if venue in _LEGACY_VENUES else None


def _without_legacy_pair(data: dict[str, Any]) -> dict[str, Any]:
    """`data` with the top-level pair moved into an entry of each venue it served
    that has none, so changing one venue afterwards leaves the other's key."""
    legacy = _pair(data)
    data.pop(_API_KEY_FIELD, None)
    data.pop(_API_SECRET_FIELD, None)
    if legacy is not None:
        entries = _entries(data)
        for venue in _LEGACY_VENUES:
            entries.setdefault(
                venue.value,
                {_API_KEY_FIELD: legacy[0], _API_SECRET_FIELD: legacy[1]},
            )
    return data
