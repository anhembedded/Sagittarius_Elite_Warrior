"""Test runs keep runtime data out of the checkout (`EPIC-030M`).

A pytest plugin, loaded by `tests/conftest.py`'s `pytest_plugins`. Two halves:

* `_runtime_data_outside_the_checkout` points `SEW_DATA_ROOT`
  (`src/core/repo_root.py`) at a session temp directory, through `os.environ`
  so a subprocess boot (`--self-check`) inherits it. Tests used to write the
  real `state/ui_state.json`, `state/bots/` — bots that restore as RUNNING on
  the next real launch — and `database/`.
* `pytest_sessionfinish` fails the run when it created `<repo>/state` or
  `<repo>/database`. Only a directory absent at session start counts, so a
  developer's real app state neither fails their run nor is touched. Under
  xdist this runs in the controller and in every worker; any of them seeing a
  leak is one. `logs/` is not checked: `ci-local.ps1` itself writes its run
  log there.

Retire when: no code path can derive a runtime directory from anything but
`data_root()`, and a guard proves it statically.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV, repo_root

_RUNTIME_DIRS = ("state", "database", "exports", "reports")
_ABSENT_AT_START = pytest.StashKey[tuple[Path, ...]]()


def pytest_sessionstart(session: pytest.Session) -> None:
    root = repo_root()
    session.config.stash[_ABSENT_AT_START] = tuple(
        root / name for name in _RUNTIME_DIRS if not (root / name).exists()
    )


def pytest_sessionfinish(session: pytest.Session) -> None:
    leaked = [
        path for path in session.config.stash.get(_ABSENT_AT_START, ()) if path.exists()
    ]
    if not leaked:
        return
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
    message = (
        f"ERROR: the test run created {', '.join(map(str, leaked))} in the "
        f"checkout; runtime files must go under {DATA_ROOT_ENV} (EPIC-030M)"
    )
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(message, red=True)
    else:
        sys.stderr.write(f"{message}\n")


@pytest.fixture(scope="session", autouse=True)
def _runtime_data_outside_the_checkout(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Path]:
    data_root = tmp_path_factory.mktemp("sew-data-root")
    previous = os.environ.get(DATA_ROOT_ENV)
    os.environ[DATA_ROOT_ENV] = str(data_root)
    yield data_root
    if previous is None:
        os.environ.pop(DATA_ROOT_ENV, None)
    else:
        os.environ[DATA_ROOT_ENV] = previous
