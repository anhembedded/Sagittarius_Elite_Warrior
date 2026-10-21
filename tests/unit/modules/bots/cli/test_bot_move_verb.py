"""`EPIC-045G` - `bot move` asks the running host and speaks its answer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_verbs import MoveBotVerb
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import build_parser
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.status_world import (
    BotQueryDispatcher,
    HeldProbe,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.verb_world import (
    RecordingHostControl,
    verb_world,
)
from sagittarius_engine.interfaces.i_config import IConfig

_PRINTER = ReportPrinter(ReportFormats.default())
S = HostControlStatus


def _run(host: RecordingHostControl, **values: object) -> CliOutcome | None:
    args = argparse.Namespace(
        **{
            "bot_id": "44wa1x",
            "venue": "spot_mainnet",
            "wait": 15.0,
            "json": True,
            "format": None,
        }
        | values
    )
    dispatcher = BotQueryDispatcher(FakeBotStore(), HeldProbe(True))
    return MoveBotVerb().run(args, verb_world(dispatcher, _PRINTER, host_control=host))


def test_move_sends_the_bot_and_the_target_venue_and_asks_no_confirmation() -> None:
    host = RecordingHostControl()

    _run(host, wait=3.0)

    assert host.sent == [
        (
            HostControlRequest(
                HostControlAction.MOVE, "44wa1x", to_venue="spot_mainnet"
            ),
            3.0,
        )
    ]
    assert host.sent[0][0].confirmed_venue is None


@pytest.mark.parametrize("missing", [None, ""])
def test_move_without_a_venue_is_a_usage_error_and_sends_nothing(
    missing: str | None,
) -> None:
    host = RecordingHostControl()

    outcome = _run(host, venue=missing)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert "--venue" in outcome.message
    assert host.sent == []


def test_a_refused_move_exits_two_in_the_hosts_words() -> None:
    host = RecordingHostControl(
        HostControlReply(S.REFUSED, "A bot's venue is fixed once it has run.")
    )

    outcome = _run(host)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert outcome.message.startswith("bot move 44wa1x: A bot's venue is fixed")


def test_an_accepted_move_prints_the_hosts_sentence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    host = RecordingHostControl(
        HostControlReply(S.DONE, "bot 44wa1x moved to spot_mainnet", "c" * 32)
    )

    outcome = _run(host)

    document = json.loads(capsys.readouterr().out)
    assert outcome is None
    assert document["data"]["action"] == "move"
    assert document["data"]["message"] == "bot 44wa1x moved to spot_mainnet"


def test_the_shipped_declaration_parses_move_and_marks_it_read_only() -> None:
    path = Path(__file__).resolve().parents[5] / "src/config/cli_commands.json"
    shipped = json.loads(path.read_text(encoding="utf-8"))["CLI_COMMANDS"]
    config = Mock(spec=IConfig)
    config.get.return_value = shipped

    args = build_parser(config).parse_args(
        ["bot", "move", "44wa1x", "--venue", "spot_mainnet"]
    )

    assert (args.action, args.bot_id, args.venue, args.wait) == (
        "move",
        "44wa1x",
        "spot_mainnet",
        15,
    )
    declared = shipped["bot"]["subparsers"]["commands"]["move"]
    assert declared["read_only"] is True
    assert "plan file is not changed" in declared["help"]
