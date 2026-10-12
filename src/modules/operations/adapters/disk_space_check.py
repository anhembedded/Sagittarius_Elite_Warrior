"""Free space where the app writes (`EPIC-038F`): a full disk breaks writes while the network works.

WARN below 1 GiB or 10 % free, FAIL below 100 MiB (research R9). It looks at the
data root and the log directory; a directory that does not exist yet is measured
through its nearest existing parent, which is the disk it will be created on.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckFinding,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_preflight_check import (
    IPreflightCheck,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)

MIB = 1024 * 1024
GIB = 1024 * MIB
WARN_BELOW_BYTES = GIB
FAIL_BELOW_BYTES = 100 * MIB
WARN_BELOW_FRACTION = 0.10


class DiskUsage(NamedTuple):
    total: int
    free: int


type UsageReader = Callable[[Path], DiskUsage]


def read_disk_usage(path: Path) -> DiskUsage:
    usage = shutil.disk_usage(path)
    return DiskUsage(usage.total, usage.free)


class DiskSpaceCheck(IPreflightCheck):
    check_id = "disk-space"
    title = "Free disk space"

    def __init__(
        self,
        targets: dict[str, Path],
        read_usage: UsageReader = read_disk_usage,
    ) -> None:
        self._targets = targets
        self._read_usage = read_usage

    def run(self, scope: PreflightScope) -> CheckResult:
        findings = tuple(
            self._look(label, path) for label, path in self._targets.items()
        )
        return CheckResult(self.check_id, self.title, findings)

    def _look(self, label: str, path: Path) -> CheckFinding:
        try:
            usage = self._read_usage(_existing_ancestor(path))
        except OSError as exc:
            return CheckFinding(
                label,
                CheckStatus.FAIL,
                f"free space of {path} could not be read ({type(exc).__name__})",
                "Check that the directory's disk is mounted and readable.",
            )
        return _judge(label, path, usage)


def _existing_ancestor(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return path


def _judge(label: str, path: Path, usage: DiskUsage) -> CheckFinding:
    fraction = usage.free / usage.total if usage.total else 0.0
    fact = f"{usage.free // MIB} MiB free of {usage.total // MIB} MiB ({fraction:.0%}) at {path}"
    if usage.free < FAIL_BELOW_BYTES:
        return CheckFinding(
            label,
            CheckStatus.FAIL,
            f"{fact}: below 100 MiB, writes will fail",
            "Free space on that disk or point SEW_DATA_ROOT at a larger one.",
        )
    if usage.free < WARN_BELOW_BYTES or fraction < WARN_BELOW_FRACTION:
        return CheckFinding(
            label,
            CheckStatus.WARN,
            f"{fact}: below 1 GiB or 10 %",
            "Free space before a long unattended run; logs and state grow.",
        )
    return CheckFinding(label, CheckStatus.PASS, fact)
