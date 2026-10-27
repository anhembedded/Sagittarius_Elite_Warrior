"""`EPIC-047C` — the application version both ends of the remote link put in their hello.

Read from `src/config/app_config.json`, the same file `load_app_config` loads, but as plain JSON:
the bridge is started for each session and the configuration loader would pull the Engine's
`ConfigManager` into its imports for one string. A version that is not there is `unknown`, and two
ends that both say `unknown` still differ in the digests of their wire roots, which is what the
handshake judges first.
"""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_FILE = Path(__file__).resolve().parents[1] / "config" / "app_config.json"
_VERSION_KEY = "app.version"
UNKNOWN_VERSION = "unknown"


def link_app_version() -> str:
    try:
        found = json.loads(_CONFIG_FILE.read_text(encoding="utf-8")).get(_VERSION_KEY)
    except (OSError, ValueError, AttributeError):
        return UNKNOWN_VERSION
    return found if isinstance(found, str) and found.strip() else UNKNOWN_VERSION
