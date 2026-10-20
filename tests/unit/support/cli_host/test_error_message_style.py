"""`BOT-198`: a failed command's sentence is red only for a person at a terminal."""

from __future__ import annotations

import io

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.error_message_style import (
    styled_error_message,
    wants_colour,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.exit_status import run_command


class _Stream:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_an_error_message_is_red_only_at_a_terminal_that_takes_colour() -> None:
    tty = _Stream(True)

    assert styled_error_message("no key", tty, {"TERM": "xterm"}) == (
        "\x1b[1;31mno key\x1b[0m"
    )
    for stream, env in (
        (_Stream(False), {"TERM": "xterm"}),
        (tty, {"TERM": "xterm", "NO_COLOR": ""}),
        (tty, {"TERM": "dumb"}),
    ):
        assert styled_error_message("no key", stream, env) == "no key"


def test_a_failure_message_to_a_pipe_is_the_plain_bytes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_command(lambda: CliOutcome(ExitCode.CONFIGURATION, "no key configured"))

    assert capsys.readouterr().err == "no key configured\n"


class _TerminalStderr(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_run_command_paints_a_failure_red_at_a_terminal_and_leaves_success_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.delenv("NO_COLOR", raising=False)

    failed = _TerminalStderr()
    monkeypatch.setattr("sys.stderr", failed)
    run_command(lambda: CliOutcome(ExitCode.CONFIGURATION, "no key configured"))
    assert failed.getvalue() == "\x1b[1;31mno key configured\x1b[0m\n"

    fine = _TerminalStderr()
    monkeypatch.setattr("sys.stderr", fine)
    run_command(lambda: CliOutcome(ExitCode.SUCCESS, "done"))
    assert fine.getvalue() == "done\n"


def test_the_one_colour_policy() -> None:
    assert wants_colour(True, {"TERM": "xterm"})
    assert not wants_colour(False, {"TERM": "xterm"})
    assert not wants_colour(True, {"TERM": "dumb"})
    assert not wants_colour(True, {"TERM": "xterm", "NO_COLOR": ""})
