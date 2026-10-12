"""The interpreter is at or above the supported floor (`EPIC-038F`).

`SUPPORTED_PYTHON_FLOOR` repeats `requires-python` in `pyproject.toml`;
`test_the_python_floor_matches_pyproject` fails when they differ.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

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

SUPPORTED_PYTHON_FLOOR = (3, 12)


def running_python() -> tuple[int, int, int]:
    return (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


class PythonFloorCheck(IPreflightCheck):
    check_id = "python-floor"
    title = "Python version"

    def __init__(
        self, running: Callable[[], tuple[int, int, int]] = running_python
    ) -> None:
        self._running = running

    def run(self, scope: PreflightScope) -> CheckResult:
        major, minor, micro = self._running()
        floor = ".".join(str(n) for n in SUPPORTED_PYTHON_FLOOR)
        if (major, minor) < SUPPORTED_PYTHON_FLOOR:
            finding = CheckFinding(
                "",
                CheckStatus.FAIL,
                f"Python {major}.{minor}.{micro} is below the supported {floor}",
                f"Install Python {floor} or newer and rebuild the environment.",
            )
        else:
            finding = CheckFinding(
                "", CheckStatus.PASS, f"Python {major}.{minor}.{micro} (floor {floor})"
            )
        return CheckResult.single(self.check_id, self.title, finding)
