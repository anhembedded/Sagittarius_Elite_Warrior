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
        """@brief Overwrites the file with exactly this key/secret pair.
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
        directory = os.path.dirname(self._filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(
                {_API_KEY_FIELD: api_key, _API_SECRET_FIELD: api_secret}, f, indent=2
            )
        try:
            os.chmod(self._filepath, 0o600)
        except OSError as exc:
            logger.warning(
                "Không đặt được quyền truy cập chỉ-chủ-sở-hữu cho %s: %s",
                self._filepath,
                exc,
            )
