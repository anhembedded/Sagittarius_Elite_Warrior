"""`EPIC-035H` — the lock dies with the process, however the process dies.

A real second process takes the lock and is killed without a chance to release
it (SIGKILL on Linux, `TerminateProcess` on Windows). The operating system
drops an advisory lock with its owner, so the next instance is the first again
and a crashed app never locks its owner out.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.infrastructure.instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.tests.instance_holder import start_holder, stop_holder


def test_the_lock_dies_with_the_process(tmp_path: Path) -> None:
    lock_file = tmp_path / "state" / "instance.lock"
    holder = start_holder(lock_file)

    while_alive = InstanceAccess.acquire(lock_file)
    holder.kill()
    holder.wait(timeout=30)
    after_death = InstanceAccess.acquire(lock_file)

    assert while_alive.read_only is True, "the live process held it"
    assert after_death.read_only is False, "the OS released it with the process"
    while_alive.release()
    after_death.release()
    stop_holder(holder)


def test_a_clean_exit_of_the_holder_frees_the_lock_too(tmp_path: Path) -> None:
    lock_file = tmp_path / "state" / "instance.lock"
    holder = start_holder(lock_file)
    assert InstanceAccess.acquire(lock_file).read_only is True

    stop_holder(holder)

    after = InstanceAccess.acquire(lock_file)
    assert after.read_only is False
    after.release()
