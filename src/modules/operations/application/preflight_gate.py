"""Whether `run` may start: the pre-flight a host runs before it serves (`EPIC-038F`).

`EPIC-038D` builds the `run` host and calls `PreflightGate.admit` once, before
anything trades; `--skip-preflight` becomes `PreflightPolicy.SKIP`. The refusal
is the same outcome the `preflight` command exits with, so a supervisor sees
one code for one fault whichever command found it.
"""

from __future__ import annotations

from enum import Enum

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import CliOutcome
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_report import (
    preflight_outcome,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_runner import (
    PreflightRunner,
)


class PreflightPolicy(Enum):
    ENFORCE = "enforce"
    SKIP = "skip"


class PreflightGate:
    def __init__(self, runner: PreflightRunner) -> None:
        self._runner = runner

    def admit(
        self, scope: PreflightScope, policy: PreflightPolicy
    ) -> CliOutcome | None:
        """`None` to go ahead; the refusing outcome when a check failed."""
        if policy is PreflightPolicy.SKIP:
            return None
        return preflight_outcome(self._runner.run(scope))
