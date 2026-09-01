"""`EPIC-021B` — reads/writes `secrets.local.json`, the gitignored fallback
for exchange credentials."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("App.Credentials")

_API_KEY_FIELD = "API_KEY"
_API_SECRET_FIELD = "API_SECRET"  # noqa: S105 - JSON field name, not a secret value


class SecretsFileSource:
    """@brief Read/write access to one local, gitignored JSON file holding
    `API_KEY`/`API_SECRET`.

    @details Same failure contract as `sagittarius_engine`'s `JsonSource`: a
    missing or malformed file reads as "nothing configured", never raises —
    a corrupt secrets file must degrade credential resolution to `NONE`, not
    crash the app.
    """

    def __init__(self, filepath: str) -> None:
        self._filepath = filepath

    def read(self) -> tuple[str, str] | None:
        """@return `(api_key, api_secret)` if the file exists, parses, and
        both fields are non-empty; `None` otherwise."""
        if not os.path.exists(self._filepath):
            return None
        try:
            with open(self._filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Không đọc được %s: %s. Coi như chưa cấu hình credentials.",
                self._filepath,
                exc,
            )
            return None

        api_key = data.get(_API_KEY_FIELD)
        api_secret = data.get(_API_SECRET_FIELD)
        if not api_key or not api_secret:
            return None
        return api_key, api_secret

    def write(self, api_key: str, api_secret: str) -> None:
        """@brief Overwrites the file with exactly this key/secret pair."""
        directory = os.path.dirname(self._filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(
                {_API_KEY_FIELD: api_key, _API_SECRET_FIELD: api_secret}, f, indent=2
            )
