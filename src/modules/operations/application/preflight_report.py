"""The `preflight` result: one `Report`, and the exit code its findings deserve (`EPIC-038F`).

The report is built from the results once; the text view and `--json` both come
from it. The outcome is separate: a failed run still prints its report (a
monitor wants the JSON of the failure) and *then* exits non-zero.

Exit code (DESIGN §7): no `FAIL` -> success. Otherwise the strongest cause among
the failed findings decides: credentials absent or refused -> 5 (never
retried), exchange out of reach -> 6 (retried after a delay), anything else -> 4.
`CAUSE_EXIT_CODE` is complete on purpose: a `CheckCause` added without a
decision here fails `test_every_cause_has_an_exit_code`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    JsonValue,
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)

COMMAND = "preflight"
SCHEMA_VERSION = 1

CAUSE_EXIT_CODE: dict[CheckCause, ExitCode] = {
    CheckCause.NONE: ExitCode.PREFLIGHT_FAILED,
    CheckCause.EXCHANGE: ExitCode.EXCHANGE,
    CheckCause.CONFIGURATION: ExitCode.CONFIGURATION,
}

_STATUS_WIDTH = 6
_ID_WIDTH = 26


def preflight_outcome(results: tuple[CheckResult, ...]) -> CliOutcome | None:
    """`None` when nothing failed, otherwise the code of the strongest cause."""
    failed = [r for r in results if r.status is CheckStatus.FAIL]
    if not failed:
        return None
    cause = max(r.cause for r in failed)
    ids = ", ".join(r.check_id for r in failed)
    return CliOutcome(CAUSE_EXIT_CODE[cause], f"pre-flight failed: {ids}")


def preflight_report(results: tuple[CheckResult, ...]) -> Report:
    return Report(
        command=COMMAND,
        version=SCHEMA_VERSION,
        payload=_payload(results),
        layout=(ReportSection(None, tuple(_rows(results))),),
    )


def _payload(results: tuple[CheckResult, ...]) -> dict[str, JsonValue]:
    outcome = preflight_outcome(results)
    counts: dict[str, JsonValue] = {
        status.name.lower(): sum(1 for r in results if r.status is status)
        for status in CheckStatus
    }
    return {
        "summary": {
            **counts,
            "exit_code": int(outcome.code) if outcome is not None else 0,
        },
        "checks": [_check_payload(r) for r in results],
    }


def _check_payload(result: CheckResult) -> JsonValue:
    return {
        "id": result.check_id,
        "title": result.title,
        "status": result.status.name,
        "origin": result.origin.value,
        "findings": [
            {
                "subject": f.subject,
                "status": f.status.name,
                "reason": f.reason,
                "remedy": f.remedy,
                "cause": f.cause.name,
            }
            for f in result.findings
        ],
    }


def _rows(results: tuple[CheckResult, ...]) -> list[ReportRow]:
    rows: list[ReportRow] = []
    for result in results:
        for finding in result.findings:
            subject = f"[{finding.subject}] " if finding.subject else ""
            rows.append(
                ReportRow(
                    (
                        ReportCell(finding.status.name, _STATUS_WIDTH),
                        ReportCell(result.check_id, _ID_WIDTH),
                        ReportCell(f"{subject}{finding.reason}"),
                    )
                )
            )
            if finding.remedy and finding.status is not CheckStatus.PASS:
                pad = " " * (_STATUS_WIDTH + _ID_WIDTH)
                rows.append(ReportRow.of(f"{pad}fix: {finding.remedy}"))
    return rows
