"""`BOT-200` — what `key check` shows and the exit status it ends with.

@details Never the key or the secret: the report is built from the venues, the
refusal and the exchange's own verdict per environment, none of which holds either
(`EnvironmentVerdict.reason` is the exchange's code and message, and a transport
failure carries only its kind). `test_key_check_cli.py` greps every outcome for a
sentinel key and secret.

Exit status follows `exit_codes.md`: a request that cannot be a key is `USAGE`; a key
the operator must replace (it can withdraw, it may not trade, the exchange refuses
it everywhere) is `CONFIGURATION`; a key nobody could judge because an environment
did not answer is `EXCHANGE`, which a retry can outlast.
"""

from __future__ import annotations

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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_check import (
    KeyCheck,
    KeyCheckRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyStanding,
)

COMMAND = "key"
REPORT_VERSION = 1

_LABEL_WIDTH = 16

REFUSAL_WORDS = {
    KeyCheckRefusal.INCOMPLETE: (
        "The key or the secret is empty. Send the key on the first line and the "
        "secret on the second."
    ),
    KeyCheckRefusal.NOT_A_KEY: (
        "The key or the secret holds a character a Binance key never has (a space, a "
        "control character or anything but printable ASCII). Nothing was asked of the "
        "exchange."
    ),
    KeyCheckRefusal.NOT_ACCEPTED: (
        "No environment accepted this key. The reason for each is below."
    ),
    KeyCheckRefusal.WITHDRAWAL_ENABLED: (
        "This mainnet key can withdraw funds. Create a new key without the "
        "withdrawal permission; never run with this one."
    ),
    KeyCheckRefusal.NO_TRADING_PERMISSION: (
        "This mainnet key may trade neither Spot nor Futures. Enable trading on the "
        "key at Binance, or create a new one."
    ),
}


def key_check_report(check: KeyCheck) -> Report:
    refusal = check.refusal
    accepted = next(
        (v for v in check.verdicts if v.standing is KeyStanding.ACCEPTED), None
    )
    environments: list[JsonValue] = [_verdict_payload(v) for v in check.verdicts]
    payload: dict[str, JsonValue] = {
        "ok": refusal is None,
        "venues": [venue.value for venue in check.venues],
        "environment": accepted.environment.value if accepted else None,
        "refusal": refusal.value if refusal else None,
        "message": REFUSAL_WORDS[refusal] if refusal else "",
        "environments": environments,
    }
    return Report(
        command=COMMAND,
        version=REPORT_VERSION,
        payload=payload,
        layout=(_result_section(check, accepted), _environments_section(check)),
    )


def key_check_outcome(check: KeyCheck) -> CliOutcome | None:
    """`None` (success) when the key is for at least one venue."""
    refusal = check.refusal
    if refusal is None:
        return None
    if refusal in (KeyCheckRefusal.INCOMPLETE, KeyCheckRefusal.NOT_A_KEY):
        return CliOutcome(ExitCode.USAGE)
    if refusal is KeyCheckRefusal.NOT_ACCEPTED and any(
        v.standing is KeyStanding.UNREACHABLE for v in check.verdicts
    ):
        return CliOutcome(ExitCode.EXCHANGE)
    return CliOutcome(ExitCode.CONFIGURATION)


def _verdict_payload(verdict: EnvironmentVerdict) -> JsonValue:
    return {
        "environment": verdict.environment.value,
        "standing": verdict.standing.value,
        "failure": verdict.failure.value if verdict.failure else None,
        "reason": verdict.reason,
    }


def _row(label: str, text: str) -> ReportRow:
    return ReportRow((ReportCell(label, _LABEL_WIDTH), ReportCell(text)))


def _result_section(
    check: KeyCheck, accepted: EnvironmentVerdict | None
) -> ReportSection:
    if check.refusal is not None:
        return ReportSection("Key", (_row("Refused", REFUSAL_WORDS[check.refusal]),))
    rows = [
        _row("Venues", ", ".join(venue.display_name for venue in check.venues)),
    ]
    if accepted is not None:
        rows.insert(0, _row("Environment", accepted.environment.label))
    rows.append(_row("Written", "nothing: this command only checks"))
    return ReportSection("Key", tuple(rows))


def _environments_section(check: KeyCheck) -> ReportSection:
    return ReportSection(
        "Environments asked",
        tuple(_row(v.environment.label, _verdict_words(v)) for v in check.verdicts),
    )


def _verdict_words(verdict: EnvironmentVerdict) -> str:
    if verdict.standing is KeyStanding.UNREACHABLE and verdict.failure is not None:
        return f"no answer ({verdict.failure.value})"
    if verdict.reason:
        return f"{verdict.standing.value}: {verdict.reason}"
    return verdict.standing.value
