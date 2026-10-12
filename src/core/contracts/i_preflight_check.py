"""One thing worth checking before the first order (`EPIC-038F`).

A check is one class that knows one fact about the machine, the key or the
exchange, and the module that knows that fact owns the class (`trading` owns
the key and the clock skew, `operations` owns disk and Python). It is declared
through `IOperationsRegistry`, never listed anywhere, so a new check is one
class and one declaration: `PreflightRunner` does not change.

The port lives in the shared kernel because the checks that matter implement it
in `trading`, and no module may import `operations` (`EPIC-038` D4).

**A check never raises on purpose and never blocks forever.** The runner turns
an exception into a `FAIL` named for the check and cuts a check off at
`deadline_seconds`, so one broken check cannot hide the others; both are still
bugs in the check, and the report says which.

@par Extension cases
  · a check for open ports, free memory or DNS — one subclass and one
    `declare_preflight` call in the module that knows the thing;
  · a check that needs a different deadline — override `deadline_seconds`;
  · a check that reads the exchange — share the read with the others through
    `PreflightScope.once`, so the exchange is asked once.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckResult,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)


class IPreflightCheck(ABC):
    #: The word `--skip` and the report use: lower-case, hyphenated, unique.
    check_id: str
    #: A short noun phrase for the report ("Clock skew against the exchange").
    title: str
    #: How long the runner waits for `run` before it reports a `FAIL`.
    deadline_seconds: float = 20.0
    #: The cause of that `FAIL`, for the exit code: a check that waits on the
    #: exchange names `EXCHANGE` (a restart can outlast it), any other waits on
    #: nothing the operator or a supervisor can tell apart, so exit 4.
    timeout_cause: CheckCause = CheckCause.NONE

    @abstractmethod
    def run(self, scope: PreflightScope) -> CheckResult:
        """Look, change nothing, and say what was found."""
