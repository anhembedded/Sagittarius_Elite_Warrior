"""The data root accepts a write (`EPIC-038F`): the check writes a probe file and removes it."""

from __future__ import annotations

import tempfile
from pathlib import Path

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

_REMEDY = (
    "Make the directory exist and writable by the account that runs the app "
    "(owner, mode, a read-only mount), or point SEW_DATA_ROOT at one that is."
)


class DataRootWritableCheck(IPreflightCheck):
    check_id = "data-root-writable"
    title = "Data root is writable"

    def __init__(self, root: Path) -> None:
        self._root = root

    def run(self, scope: PreflightScope) -> CheckResult:
        return CheckResult.single(self.check_id, self.title, self._finding())

    def _finding(self) -> CheckFinding:
        if not self._root.is_dir():
            return CheckFinding(
                "data root",
                CheckStatus.FAIL,
                f"{self._root} is not a directory",
                _REMEDY,
            )
        try:
            with tempfile.NamedTemporaryFile(
                dir=self._root, prefix=".preflight-probe-"
            ):
                pass
        except OSError as exc:
            return CheckFinding(
                "data root",
                CheckStatus.FAIL,
                f"a probe file could not be written in {self._root} ({type(exc).__name__})",
                _REMEDY,
            )
        return CheckFinding(
            "data root",
            CheckStatus.PASS,
            f"a probe file was written and removed in {self._root}",
        )
