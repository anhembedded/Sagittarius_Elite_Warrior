"""What the process-level `run` tests share (`EPIC-038D`).

Two files drive a real `main.py run` child (`test_run_process.py`: its signals, pre-flight and
exit codes; `test_run_process_beside_other_processes.py`: a second process holding the lock, one
reading its snapshot, and one killing it). The child itself is `tests/run_host_child.py`; this is
the small kit around it.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_probe import (
    FileLockInstanceProbe,
)
from Sagittarius_Elite_Warrior.tests.run_host_child import (
    CHILD_SCRIPT,
    DEFAULT_CREDENTIALS,
    START_BUDGET_SECONDS,
    RunChild,
    child_environment,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

#: A stop policy that never finishes by itself, as one waiting on a slow exchange would:
#: the host's timeout and the second signal are what end it.
HANGING_POLICY = """
from Sagittarius_Elite_Warrior.src.modules.operations.adapters import leave_orders_resting

def _hang(self, ledger, give_up):
    ledger.begin("bot-x", "STOPPING", 3)
    give_up.wait(3600)

leave_orders_resting.LeaveOrdersResting.apply = _hang
"""

#: A disk with nothing free, as `DiskSpaceCheck` would read a full one.
FULL_DISK = """
import shutil
shutil.disk_usage = lambda path: shutil._ntuple_diskusage(10_000_000_000, 1_000_000_000, 0)
"""


@contextmanager
def fake_exchange() -> Iterator[FakeServerUrls]:
    with run_binance_fake_server() as urls:
        yield urls


@contextmanager
def children_to_reap() -> Iterator[list[RunChild]]:
    """Children a test started; any still alive is killed, so a failure leaks no process."""
    children: list[RunChild] = []
    try:
        yield children
    finally:
        for child in children:
            child.kill()


def start_child(
    started: list[RunChild],
    data_root: Path,
    urls: FakeServerUrls,
    *args: str,
    **kwargs: object,
) -> RunChild:
    child = RunChild(data_root, urls, *args, **kwargs)  # type: ignore[arg-type]
    started.append(child)
    return child


def status_json(
    data_root: Path, urls: FakeServerUrls
) -> subprocess.CompletedProcess[str]:
    """`main.py status --json` in its own process, beside the host."""
    return subprocess.run(
        [sys.executable, "-c", CHILD_SCRIPT, "status", "--json"],
        cwd=str(Path(__file__).resolve().parents[3].parent),
        capture_output=True,
        text=True,
        timeout=START_BUDGET_SECONDS,
        check=False,
        env=child_environment(data_root, urls, DEFAULT_CREDENTIALS),
    )


def transitions(text: str) -> list[str]:
    return [
        line.split("[host] ", 1)[1].strip()
        for line in text.splitlines()
        if "[host] " in line and " -> " in line
    ]


def lock_is_free(data_root: Path) -> bool:
    return not FileLockInstanceProbe(data_root / "state" / "instance.lock").is_held()
