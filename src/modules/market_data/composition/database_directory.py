"""Where market_data's SQLite shards go — `database.dir`, `SEW_DATA_ROOT`, or `./database`.

@details Precedence, first match wins (`EPIC-030M`):

| `database.dir` | `SEW_DATA_ROOT` | Directory |
| :--- | :--- | :--- |
| `":memory:"` or an absolute path | any | the configured value, verbatim |
| relative or unset | set | `<SEW_DATA_ROOT>/database` |
| relative | unset | the configured value, verbatim (relative to the cwd) |
| unset | unset | `<cwd>/database` |

With `SEW_DATA_ROOT` unset this is byte-identical to the previous
`config.get(...) or os.path.join(os.getcwd(), "database")`. A relative value is
what the shipped `app_config.json` holds (`"Sagittarius_Elite_Warrior/database"`,
resolved against the cwd), so it is the case the override must win over for a
test boot to stay out of the checkout; an absolute path or the in-memory
sentinel is an explicit choice a test or a user made, and is honoured.
"""

from __future__ import annotations

import os
from pathlib import Path

from sagittarius_engine.extensions.persistence.sqlite_shard_manager import IN_MEMORY

#: The directory name used under the cwd or under `SEW_DATA_ROOT`.
DEFAULT_DB_DIR_NAME = "database"


def database_directory(
    configured: str | None, data_root_override: Path | None, cwd: str
) -> str:
    """The shard directory for `configured` (`database.dir`), the
    `SEW_DATA_ROOT` override (`core.repo_root.data_root_override()`) and the
    process's working directory — see this module's table."""
    if configured and (configured == IN_MEMORY or os.path.isabs(configured)):
        return configured
    if data_root_override is not None:
        return str(data_root_override / DEFAULT_DB_DIR_NAME)
    if configured:
        return configured
    return os.path.join(cwd, DEFAULT_DB_DIR_NAME)
