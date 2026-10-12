"""One mapping from a command's result to the process exit status (`EPIC-038B`)."""

from __future__ import annotations

import argparse
import logging
import traceback

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.exit_status import (
    exit_status_of,
    run_command,
)
from sagittarius_engine import App


class _SilentHandler(ICliCommandHandler):
    """A handler written before the contract: returns nothing, means success."""

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> None:
        del args, app


class _FailingHandler(ICliCommandHandler):
    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> CliOutcome | None:
        del args, app
        return CliOutcome(ExitCode.CONFIGURATION, "no key configured")


def test_a_handler_returning_none_exits_zero() -> None:
    status = run_command(lambda: _SilentHandler.handle(argparse.Namespace(), None))  # type: ignore[arg-type]

    assert status == 0


def test_a_returned_outcome_is_its_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = run_command(lambda: _FailingHandler.handle(argparse.Namespace(), None))  # type: ignore[arg-type]

    assert status == int(ExitCode.CONFIGURATION)
    assert capsys.readouterr().err.strip() == "no key configured"


def test_a_success_outcome_exits_zero_and_says_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_command(lambda: CliOutcome(ExitCode.SUCCESS)) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("code", list(ExitCode))
def test_every_documented_code_is_the_status_it_names(code: ExitCode) -> None:
    assert exit_status_of(CliOutcome(code)) == int(code)


def test_an_unknown_exception_exits_one_and_logs_the_traceback(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    def explode() -> CliOutcome | None:
        raise RuntimeError("the database is gone")

    with caplog.at_level(logging.ERROR, logger="App.CliHost"):
        status = run_command(explode)

    assert status == int(ExitCode.ERROR)
    (record,) = [r for r in caplog.records if r.name == "App.CliHost"]
    assert record.exc_info is not None
    assert "the database is gone" in "".join(
        traceback.format_exception(*record.exc_info)
    )
    assert "the database is gone" in capsys.readouterr().err


def test_a_system_exit_keeps_the_status_it_carries() -> None:
    """argparse exits 2 and the desktop application exits with its own code;
    neither is an "unexpected error" to relabel as 1."""

    def usage_error() -> CliOutcome | None:
        raise SystemExit(2)

    with pytest.raises(SystemExit) as raised:
        run_command(usage_error)

    assert raised.value.code == 2
