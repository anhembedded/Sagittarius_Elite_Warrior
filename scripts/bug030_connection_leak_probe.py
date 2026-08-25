"""BUG-030 diagnostic: name the test that leaves a SQLite connection open.

`BUG-030` is a Windows-only crash: an xdist worker dies mid-suite right after
``ResourceWarning: unclosed database``, with no pytest summary. The warning is
raised from GC finalization, so pytest's ``unraisableexception`` plugin pins it
on whichever test happened to be running at that moment -- an innocent
bystander, not the leak source. That is why reading the traceback has never
identified the culprit.

This probe removes the guesswork. It records the connection each test opens and
checks, after that test's real teardown, whether anything closed it. It reads
the connection's own state instead of waiting for GC, so it does not depend on
the platform-specific finalization timing that makes the crash Windows-only.

Usage (run from the workspace root, the directory containing this repo)::

    PYTHONPATH=. QT_QPA_PLATFORM=offscreen BUG030_OUT=/tmp/b030 \
      Sagittarius_Elite_Warrior/.venv/bin/python -m pytest \
      Sagittarius_Elite_Warrior/tests \
      --ignore=Sagittarius_Elite_Warrior/tests/sanity \
      --ignore=Sagittarius_Elite_Warrior/tests/integration/presentation/ui \
      -n 6 -p Sagittarius_Elite_Warrior.scripts.bug030_connection_leak_probe

``BUG030_OUT`` is required under ``-n``: xdist swallows worker stdout, so each
worker writes ``<BUG030_OUT>.<worker-id>`` instead. Without ``-n`` the report is
printed at session end.

Three traps cost real time when this probe was built. All three produce a
confident, totally wrong "no leaks found", so do not remove the workarounds:

1. ``sqlite3.Connection`` is **not weak-referenceable** -- ``weakref.ref()``
   raises ``TypeError``. This probe therefore holds strong references, which
   also makes it stricter in the direction we want: a connection it reports
   OPEN is one nothing *explicitly* closed. Leaving it to GC is precisely the
   condition that produces the Windows ResourceWarning.
2. SQLAlchemy's pysqlite dialect calls ``sqlite3.dbapi2.connect``, a **distinct
   module attribute** from ``sqlite3.connect`` even though both name the same
   builtin. Patching only the latter intercepts nothing.
3. ``pytest_runtest_teardown`` must be a **hookwrapper**. A plain implementation
   races pytest's own teardown hook and can run before the fixture finalizers,
   reporting connections the fixture was about to close -- that false-positive
   run wrongly accused ``test_sqlalchemy_repository.py``, whose ``repo`` fixture
   is in fact correct.
"""

from __future__ import annotations

import os
import sqlite3
import sqlite3.dbapi2 as _dbapi2
import traceback
from collections.abc import Generator
from typing import Any

import pytest

_TRACKED: list[tuple[sqlite3.Connection, str, str, str]] = []
_LEAKS: list[tuple[str, int, str, str]] = []
_CURRENT: dict[str, str] = {"nodeid": "<import/collection>"}
_STACK_DEPTH = 18
_real_connect = sqlite3.connect


def _is_open(conn: sqlite3.Connection) -> bool:
    """@brief True while the connection still accepts operations.

    @details ``total_changes`` raises ``ProgrammingError`` once closed, so it is a
    read-only liveness probe that cannot itself alter database state.
    """
    try:
        _ = conn.total_changes
    except sqlite3.ProgrammingError:
        return False
    return True


def _tracking_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
    conn = _real_connect(*args, **kwargs)
    database = args[0] if args else kwargs.get("database", "?")
    _TRACKED.append(
        (
            conn,
            _CURRENT["nodeid"],
            str(database),
            "".join(traceback.format_stack(limit=_STACK_DEPTH)[:-1]),
        )
    )
    return conn


sqlite3.connect = _tracking_connect  # type: ignore[assignment]
_dbapi2.connect = _tracking_connect  # type: ignore[assignment]


def pytest_runtest_setup(item: pytest.Item) -> None:
    _CURRENT["nodeid"] = item.nodeid


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Generator[None, Any, None]:
    """@brief Checks for unclosed connections after real teardown has finished.

    @details Must stay a hookwrapper -- see trap 3 in the module docstring.
    """
    yield
    leaked = [t for t in _TRACKED if t[1] == item.nodeid and _is_open(t[0])]
    if leaked:
        _LEAKS.append((item.nodeid, len(leaked), leaked[0][2], leaked[0][3]))
    _CURRENT["nodeid"] = "<between tests>"


def _relevant_frames(stack: str) -> list[str]:
    keep = []
    for line in stack.strip().split("\n"):
        is_ours = "Sagittarius_Elite_Warrior" in line or "sagittarius_engine" in line
        if is_ours and "/.venv/" not in line and "site-packages" not in line:
            keep.append(line.strip())
    return keep


def _write_worker_report(destination: str, worker: str) -> None:
    with open(f"{destination}.{worker}", "w", encoding="utf-8") as handle:
        handle.write(f"worker={worker} opened={len(_TRACKED)} leaks={len(_LEAKS)}\n")
        for nodeid, count, database, stack in _LEAKS:
            handle.write(f"LEAK {nodeid} n={count} db={database}\n")
            handle.writelines(f"    {frame}\n" for frame in _relevant_frames(stack))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    destination = os.environ.get("BUG030_OUT")
    if destination:
        _write_worker_report(destination, worker)

    print("\n" + "=" * 74)
    print(f"BUG-030 connection-leak probe [{worker}]")
    print(f"  connections opened          : {len(_TRACKED)}")
    print(f"  tests leaving one unclosed  : {len(_LEAKS)}")
    print("=" * 74)
    for nodeid, count, database, stack in _LEAKS:
        print(f"\n### {nodeid}\n    left open: {count}   db={database}")
        for frame in _relevant_frames(stack):
            print(f"    {frame}")
