"""The prompt tells the operator what a command refused, and keeps running (`EPIC-038B`).

A handler now returns a `CliOutcome`. The prompt must not let a refusal vanish:
`exchange-status --format xml` used to print nothing at all, because the only
sentence naming the problem lives in the returned outcome.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    ICliCommandTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.handlers.exchange_status_cli_handler import (
    ExchangeStatusCliHandler,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.interactive_shell import (
    InteractiveShell,
)
from Sagittarius_Elite_Warrior.src.shell.app_config import CLI_COMMANDS_FILE
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.presentation.cli.golden_cases import (
    EXCHANGE_STATUS_CASES,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_config import IConfig


def _shell() -> InteractiveShell:
    config = ConfigManager()
    config.load_json(str(CLI_COMMANDS_FILE))
    table = Mock(spec=ICliCommandTable)
    table.handlers.return_value = {}
    snapshot = FakeAccountSnapshot(EXCHANGE_STATUS_CASES["futures_key_rejected"])
    app = Mock()
    app.container.resolve.side_effect = lambda port: {
        IConfig: config,
        ICliCommandTable: table,
        IAccountSnapshot: snapshot,
        IReportFormats: ReportFormats.default(),
    }[port]
    shell = InteractiveShell(app)
    shell.handlers = {"exchange-status": ExchangeStatusCliHandler}
    return shell


def test_a_usage_refusal_is_printed_to_stderr_and_the_session_goes_on(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stop = _shell().default("exchange-status --format xml")

    captured = capsys.readouterr()
    assert "unknown format 'xml'" in captured.err
    assert "Connection" not in captured.out
    assert not stop  # a truthy return would end the cmdloop


def test_a_failed_command_that_already_printed_its_report_adds_no_second_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stop = _shell().default("exchange-status")

    captured = capsys.readouterr()
    assert "KEY_REJECTED" in captured.out
    assert captured.err == ""
    assert not stop
