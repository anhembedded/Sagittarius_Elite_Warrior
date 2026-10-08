"""A second process that holds a data root's instance lock (`EPIC-035H`).

Shared by the test that kills it to prove the lock dies with the process
(`tests/integration/infrastructure/`) and by the sanity test that boots the
real entry point beside it. A real process, because an advisory lock is
per-process: two locks in one process say nothing about two copies of the app.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_PARENT = Path(__file__).resolve().parents[2]

_HOLDER = """
import sys
from pathlib import Path
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import InstanceAccess

access = InstanceAccess.acquire(Path(sys.argv[1]))
print("read-only" if access.read_only else "holding", flush=True)
sys.stdin.read()
"""


def start_holder(lock_file: Path) -> subprocess.Popen[str]:
    """Starts a process that locks `lock_file` and waits; returns once it holds it.
    Close its stdin to let it exit, or `kill()` it."""
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(lock_file)],
        cwd=str(_REPO_PARENT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None
    said = holder.stdout.readline().strip()
    assert said == "holding", f"the holder process said {said!r}, not 'holding'"
    return holder


def stop_holder(holder: subprocess.Popen[str]) -> None:
    """Lets the holder exit cleanly and reaps it (harmless if it was killed)."""
    if holder.stdin is not None:
        holder.stdin.close()
    if holder.stdout is not None:
        holder.stdout.close()
    holder.wait(timeout=30)
