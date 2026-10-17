"""The exit-code table as documentation, generated from the enum.

`EPIC-038B`. Prose that restates a number drifts from the code that returns
it. Each `ExitCode` has a row here (a test fails for a member without one) and
`Docs/OPERATIONS/exit_codes.md` is the rendered table (a second test compares
the file with the render, so a hand edit or a new member fails until the file
is regenerated with `python3 scripts/render_exit_codes.py --write`). The
runbook (`EPIC-038H`) links the file and takes `RestartPreventExitStatus` from
`non_restarting_codes()` instead of retyping the numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode


class SupervisorAction(Enum):
    NONE = "—"
    RESTART = "restarted"
    RESTART_AFTER_DELAY = "restarted with a delay"
    DO_NOT_RESTART = "not restarted"


@dataclass(frozen=True, slots=True)
class ExitCodeRow:
    meaning: str
    used_by: str
    supervisor: SupervisorAction


EXIT_CODE_TABLE: dict[ExitCode, ExitCodeRow] = {
    ExitCode.SUCCESS: ExitCodeRow(
        "success, or a clean shutdown", "all", SupervisorAction.NONE
    ),
    ExitCode.ERROR: ExitCodeRow(
        "unexpected error: a failure nothing named (an unhandled exception has its traceback in the log)",
        "all",
        SupervisorAction.RESTART,
    ),
    ExitCode.USAGE: ExitCodeRow(
        "usage error or a designed refusal: a bad flag, an unknown format, a request that "
        "cannot be an order, or a command that declined to act (no data to work on yet, "
        "a safety limit); repeating it unchanged cannot help",
        "all",
        SupervisorAction.DO_NOT_RESTART,
    ),
    ExitCode.LOCK_HELD: ExitCodeRow(
        "another copy holds the data root",
        "`run`, mutating commands",
        SupervisorAction.DO_NOT_RESTART,
    ),
    ExitCode.PREFLIGHT_FAILED: ExitCodeRow(
        "a pre-flight check failed that is neither of the two below: the machine (disk, data "
        "root, Python), a clock skew the check measured over its threshold, a key without "
        "trading permission",
        "`run`, `preflight`",
        SupervisorAction.DO_NOT_RESTART,
    ),
    ExitCode.CONFIGURATION: ExitCodeRow(
        "only the operator can fix it, so a restart would repeat it: no key, a key the exchange "
        "rejects (`-2015`: key, address or permission), a bad signature (`-1022`), a key that can "
        "withdraw, Hedge Mode",
        "`run`, `preflight`, `exchange-status`, trade commands, `bot stop`, `bot pause`, "
        "`bot resume`, `bot start`, `bot delete` (this account has no control over the running host)",
        SupervisorAction.DO_NOT_RESTART,
    ),
    ExitCode.EXCHANGE: ExitCodeRow(
        "the exchange was unreachable or out of service, or rejected the clock (`-1021`, which "
        "resyncs): a restart can outlast it",
        "commands that touch the exchange",
        SupervisorAction.RESTART_AFTER_DELAY,
    ),
    ExitCode.HOST_NOT_RUNNING: ExitCodeRow(
        "no host is running",
        "`status`, `bot stop`, `bot pause`, `bot resume`, `bot start`, `bot delete`",
        SupervisorAction.NONE,
    ),
    ExitCode.HOST_UNHEALTHY: ExitCodeRow(
        "a host is running but unhealthy (snapshot stale, a section unavailable or degraded), "
        "or a control command got no recorded answer in time",
        "`status`, `bot stop`, `bot pause`, `bot resume`, `bot start`, `bot delete`",
        SupervisorAction.NONE,
    ),
}


def non_restarting_codes() -> tuple[int, ...]:
    """The statuses a supervisor must not restart on (`RestartPreventExitStatus`)."""
    return tuple(
        int(code)
        for code, row in EXIT_CODE_TABLE.items()
        if row.supervisor is SupervisorAction.DO_NOT_RESTART
    )


def render_exit_code_markdown() -> str:
    """The table as the Markdown `Docs/OPERATIONS/exit_codes.md` holds."""
    lines = [
        "| Code | Name | Meaning | Used by | Supervisor |",
        "| :-: | :--- | :--- | :--- | :--- |",
    ]
    for code in ExitCode:
        row = EXIT_CODE_TABLE[code]
        lines.append(
            f"| {int(code)} | `{code.name}` | {row.meaning} | {row.used_by} "
            f"| {row.supervisor.value} |"
        )
    return "\n".join(lines) + "\n"
