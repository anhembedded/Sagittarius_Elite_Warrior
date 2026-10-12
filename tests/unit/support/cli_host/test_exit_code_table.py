"""The exit-code table cannot differ from the enum or from its document (`EPIC-038B`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.scripts.render_exit_codes import (
    DOCUMENT,
    render_document,
)
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.support.cli_host.exit_code_table import (
    EXIT_CODE_TABLE,
    non_restarting_codes,
    render_exit_code_markdown,
)


def test_every_exit_code_has_a_row_and_no_row_is_orphaned() -> None:
    assert set(EXIT_CODE_TABLE) == set(ExitCode)


def test_the_exit_code_numbers_are_the_documented_ones() -> None:
    """Pinned on purpose: a supervisor's restart policy is keyed on these
    numbers, so changing one is a decision, not a refactor."""
    assert {code.name: int(code) for code in ExitCode} == {
        "SUCCESS": 0,
        "ERROR": 1,
        "USAGE": 2,
        "LOCK_HELD": 3,
        "PREFLIGHT_FAILED": 4,
        "CONFIGURATION": 5,
        "EXCHANGE": 6,
        "HOST_NOT_RUNNING": 10,
        "HOST_UNHEALTHY": 11,
    }


def test_the_exit_code_table_in_the_runbook_source_matches_the_enum() -> None:
    """`Docs/OPERATIONS/exit_codes.md` is generated; a hand edit, or an enum
    member added without regenerating, fails here. Regenerate with
    `python3 scripts/render_exit_codes.py --write`."""
    assert DOCUMENT.read_text(encoding="utf-8") == render_document()


def test_every_member_appears_in_the_rendered_table() -> None:
    table = render_exit_code_markdown()

    assert all(f"| {int(code)} | `{code.name}` |" in table for code in ExitCode)


def test_a_configuration_error_is_never_restarted_and_an_exchange_error_is_retried() -> (
    None
):
    """DESIGN §7: a restart loop on a bad configuration is the failure this
    table exists to prevent; the exchange being down is worth another try."""
    prevent = set(non_restarting_codes())

    assert {int(ExitCode.LOCK_HELD), int(ExitCode.PREFLIGHT_FAILED)} <= prevent
    assert int(ExitCode.CONFIGURATION) in prevent
    assert int(ExitCode.EXCHANGE) not in prevent
    assert int(ExitCode.ERROR) not in prevent
