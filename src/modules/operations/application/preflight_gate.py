"""Whether `run` may start: the pre-flight a host runs before it serves (`EPIC-038F`).

`EPIC-038D` builds the `run` host and calls `PreflightGate.admit` once, before
anything trades; `--skip-preflight` becomes `PreflightPolicy.SKIP`. The refusal
is the same outcome the `preflight` command exits with, so a supervisor sees
one code for one fault whichever command found it.
"""

from __future__ import annotations

import logging
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckResult,
    CheckStatus,
)
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

logger = logging.getLogger("App.Operations.Preflight")


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
            logger.warning(
                "[preflight] --skip-preflight: no check ran; the host serves without "
                "knowing the key, the clock or the exchange are fit"
            )
            return None
        results = self._runner.run(scope)
        _log_findings(results)
        return preflight_outcome(results)


def _log_findings(results: tuple[CheckResult, ...]) -> None:
    """A service's only output is its log: say why it refused, and what to do."""
    for result in results:
        for finding in result.findings:
            if finding.status is CheckStatus.PASS:
                continue
            level = (
                logging.ERROR if finding.status is CheckStatus.FAIL else logging.WARNING
            )
            logger.log(
                level,
                "[preflight] %s %s%s: %s%s",
                finding.status.name,
                result.check_id,
                f" [{finding.subject}]" if finding.subject else "",
                finding.reason,
                f" - fix: {finding.remedy}" if finding.remedy else "",
            )
