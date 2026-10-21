"""`EPIC-045G` - `bot arm-strategy` and `bot disarm-strategy` ask the running host and speak its answer."""

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
    STRATEGY_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_verbs import (
    ArmStrategyVerb,
    DisarmStrategyVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.i_bot_verb import IBotVerb
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


def _run(
    verb: IBotVerb, host: RecordingHostControl, **values: object
) -> CliOutcome | None:
    args = argparse.Namespace(
        **{"venue": "spot_testnet", "wait": 15.0, "json": True, "format": None} | values
    )
    dispatcher = BotQueryDispatcher(FakeBotStore(), HeldProbe(True))
    return verb.run(args, verb_world(dispatcher, _PRINTER, host_control=host))


def test_arm_sends_the_venue_the_typed_venue_and_the_strategy_subject() -> None:
    host = RecordingHostControl()

    _run(
        ArmStrategyVerb(),
        host,
        venue="spot_mainnet",
        confirm_venue="spot_mainnet",
        wait=3.0,
    )

    assert host.sent == [
        (
            HostControlRequest(
                HostControlAction.ARM_STRATEGY,
                STRATEGY_SUBJECT,
                "spot_mainnet",
                strategy_venue="spot_mainnet",
            ),
            3.0,
        )
    ]


def test_disarm_sends_the_venue_and_no_confirmation() -> None:
    host = RecordingHostControl()

    _run(DisarmStrategyVerb(), host, venue="spot_mainnet")

    request = host.sent[0][0]
    assert request.action is HostControlAction.DISARM_STRATEGY
    assert request.strategy_venue == "spot_mainnet" and request.confirmed_venue is None


@pytest.mark.parametrize("verb", [ArmStrategyVerb(), DisarmStrategyVerb()])
@pytest.mark.parametrize("missing", [None, ""])
def test_a_missing_venue_is_a_usage_error_and_sends_nothing(
    verb: IBotVerb, missing: str | None
) -> None:
    host = RecordingHostControl()

    outcome = _run(verb, host, venue=missing)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert "--venue" in outcome.message
    assert host.sent == []


def test_a_refused_arm_exits_two_in_the_hosts_words() -> None:
    host = RecordingHostControl(
        HostControlReply(S.REFUSED, "no saved arming exists for spot_testnet")
    )

    outcome = _run(ArmStrategyVerb(), host)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert outcome.message.startswith("bot arm-strategy strategy: no saved arming")


def test_an_accepted_arm_prints_the_hosts_sentence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    host = RecordingHostControl(
        HostControlReply(S.DONE, "strategy armed on spot_testnet: x", "c" * 32)
    )

    outcome = _run(ArmStrategyVerb(), host)

    document = json.loads(capsys.readouterr().out)
    assert outcome is None
    assert document["data"]["action"] == "arm-strategy"
    assert document["data"]["message"] == "strategy armed on spot_testnet: x"


def test_the_shipped_declarations_parse_and_are_read_only() -> None:
    path = Path(__file__).resolve().parents[5] / "src/config/cli_commands.json"
    shipped = json.loads(path.read_text(encoding="utf-8"))["CLI_COMMANDS"]
    config = Mock(spec=IConfig)
    config.get.return_value = shipped
    parser = build_parser(config)

    arm = parser.parse_args(
        [
            "bot",
            "arm-strategy",
            "--venue",
            "spot_mainnet",
            "--confirm-venue",
            "spot_mainnet",
        ]
    )
    disarm = parser.parse_args(["bot", "disarm-strategy", "--venue", "spot_testnet"])

    assert (arm.action, arm.venue, arm.confirm_venue) == (
        "arm-strategy",
        "spot_mainnet",
        "spot_mainnet",
    )
    assert (disarm.action, disarm.venue) == ("disarm-strategy", "spot_testnet")
    declared = shipped["bot"]["subparsers"]["commands"]
    assert declared["arm-strategy"]["read_only"] is True
    assert declared["disarm-strategy"]["read_only"] is True
