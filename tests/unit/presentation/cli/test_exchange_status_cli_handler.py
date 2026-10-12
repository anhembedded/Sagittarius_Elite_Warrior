"""`exchange-status` at the prompt is the headless command, not a copy of it (`EPIC-038B`)."""

from __future__ import annotations

import argparse
import json
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
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
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import (
    build_handler_parser,
    build_parser,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.handlers.exchange_status_cli_handler import (
    ExchangeStatusCliHandler,
)
from Sagittarius_Elite_Warrior.src.shell.app_config import CLI_COMMANDS_FILE
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.presentation.cli.golden_cases import (
    EXCHANGE_STATUS_CASES,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


def _app(status_case: str) -> Mock:
    snapshot = FakeAccountSnapshot(EXCHANGE_STATUS_CASES[status_case])
    app = Mock()
    app.container.resolve.side_effect = lambda port: {
        IAccountSnapshot: snapshot,
        IReportFormats: ReportFormats.default(),
    }[port]
    return app


def test_the_prompt_honours_json_instead_of_ignoring_the_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = argparse.Namespace(json=True, format=None)

    outcome = ExchangeStatusCliHandler.handle(args, _app("futures_key_rejected"))

    assert outcome == CliOutcome(ExitCode.EXCHANGE)
    assert json.loads(capsys.readouterr().out)["data"]["failure"] == "key_rejected"


def test_the_prompt_prints_the_text_report_by_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = argparse.Namespace(json=False, format=None)

    outcome = ExchangeStatusCliHandler.handle(
        args, _app("futures_success_without_summary")
    )

    assert outcome is None
    assert "Connection: ✔" in capsys.readouterr().out


def _commands() -> ConfigManager:
    config = ConfigManager()
    config.load_json(str(CLI_COMMANDS_FILE))
    return config


def test_both_parsers_accept_json_and_a_free_format_word_for_each_report_command() -> (
    None
):
    """A third renderer is selected by `--format <its name>`: the parser must
    take any word, so registering a renderer never edits `cli_commands.json`."""
    config = _commands()
    assert config.get(ConfigKeys.CLI_COMMANDS.value)  # the file was found

    headless = build_parser(config)
    prompt = build_handler_parser(config, "exchange-status")

    assert headless.parse_args(["exchange-status", "--json"]).json is True
    assert headless.parse_args(["exchange-status", "--format", "kv"]).format == "kv"
    assert prompt.parse_args(["--format", "kv"]).format == "kv"
    preview = ["order-preview", "--symbol", "BTCUSDT", "--side", "BUY", "--qty", "1"]
    preview += ["--price", "1", "--format", "kv"]
    assert headless.parse_args(preview).format == "kv"
