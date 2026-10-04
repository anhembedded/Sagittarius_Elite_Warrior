"""The repository root, found by its landmark, and the root runtime data goes under.

@details `pyproject.toml` marks the root; the search walks up from this
file, so it is correct wherever the app was launched from and wherever this
file moves (`test_no_root_is_found_by_counting.py` refuses counting parent
directories).

`data_root()` is where the app keeps the files it writes at run time — the
gitignored `state/` (`ui_state.json`, `bots`' store, `trading`'s inventory
checkpoints), the dev/debug `logs/` and, when overridden, `database/`. It is
the repository root unless `SEW_DATA_ROOT` names another directory (the name
mirrors `SEW_TESTNET_TESTS`). The variable exists so a test run — including a
subprocess boot, which inherits the environment — never writes into the real
checkout's app state (`EPIC-030M`: tests used to write bots that restore as
RUNNING). Plausible next cases, each one line here: a packaged build's
per-user data directory; a `--data-root` command-line flag.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

_LANDMARK = "pyproject.toml"

#: The environment variable that moves every runtime file out of the repo.
DATA_ROOT_ENV = "SEW_DATA_ROOT"

logger = logging.getLogger("App.DataRoot")


def repo_root() -> Path:
    """The directory holding `pyproject.toml`, searching up from this file."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / _LANDMARK).is_file():
            return candidate
    raise FileNotFoundError(f"No {_LANDMARK} above {__file__}")


def data_root_override() -> Path | None:
    """`SEW_DATA_ROOT` when set and non-empty, else `None`."""
    value = os.environ.get(DATA_ROOT_ENV, "")
    return Path(value) if value else None


def data_root() -> Path:
    """Where runtime files go: `SEW_DATA_ROOT` if set, else the repository root."""
    override = data_root_override()
    if override is None:
        root = repo_root()
        logger.debug("[data-root] %s (repository root; %s unset)", root, DATA_ROOT_ENV)
        return root
    logger.info("[data-root] %s (overridden by %s)", override, DATA_ROOT_ENV)
    return override
