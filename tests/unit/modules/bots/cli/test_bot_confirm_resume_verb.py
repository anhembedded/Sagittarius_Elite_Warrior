"""`EPIC-045G` - `bot confirm-resume` asks the running host and carries the typed venue."""

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
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_verbs import (
    ConfirmResumeBotVerb,
)
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
            "proposal": "1a2b3c4d",
            "wait": 15.0,
            "json": True,
            "format": None,
        }
        | values
    )
    dispatcher = BotQueryDispatcher(FakeBotStore(), HeldProbe(True))
    return ConfirmResumeBotVerb().run(
        args, verb_world(dispatcher, _PRINTER, host_control=host)
    )


def test_confirm_resume_sends_the_bot_and_the_typed_venue() -> None:
    host = RecordingHostControl()

    _run(host, wait=3.0, confirm_venue="spot_mainnet", proposal="1a2b3c4d")

    assert host.sent == [
        (
            HostControlRequest(
                HostControlAction.CONFIRM_RESUME,
                "44wa1x",
                "spot_mainnet",
                proposal="1a2b3c4d",
            ),
            3.0,
        )
    ]


def test_a_refused_confirmation_exits_two_in_the_hosts_words() -> None:
    host = RecordingHostControl(
        HostControlReply(S.REFUSED, "Bot 44wa1x holds no resume proposal")
    )

    outcome = _run(host)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert outcome.message.startswith("bot confirm-resume 44wa1x: Bot 44wa1x holds no")


def test_an_accepted_confirmation_prints_the_hosts_sentence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    host = RecordingHostControl(
        HostControlReply(S.DONE, "the confirmation is queued", "c" * 32)
    )

    outcome = _run(host)

    document = json.loads(capsys.readouterr().out)
    assert outcome is None
    assert document["data"]["action"] == "confirm-resume"
    assert document["data"]["message"] == "the confirmation is queued"


def test_the_shipped_declaration_parses_confirm_resume_and_the_typed_venue() -> None:
    path = Path(__file__).resolve().parents[5] / "src/config/cli_commands.json"
    shipped = json.loads(path.read_text(encoding="utf-8"))["CLI_COMMANDS"]
    config = Mock(spec=IConfig)
    config.get.return_value = shipped

    args = build_parser(config).parse_args(
        [
            "bot",
            "confirm-resume",
            "44wa1x",
            "--proposal",
            "1a2b3c4d",
            "--confirm-venue",
            "spot_mainnet",
        ]
    )

    assert (args.action, args.bot_id, args.proposal, args.confirm_venue) == (
        "confirm-resume",
        "44wa1x",
        "1a2b3c4d",
        "spot_mainnet",
    )
    declared = shipped["bot"]["subparsers"]["commands"]["confirm-resume"]
    assert declared["read_only"] is True


@pytest.mark.parametrize("missing", [None, ""])
def test_a_missing_proposal_is_a_usage_error_and_sends_nothing(
    missing: str | None,
) -> None:
    host = RecordingHostControl()

    outcome = _run(host, proposal=missing)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert "--proposal <fingerprint>" in outcome.message
    assert host.sent == []
