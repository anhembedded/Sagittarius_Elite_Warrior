"""`bot stop`, `bot pause` and `bot resume` ask the running host and speak its answer (`EPIC-038J`)."""

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
    LOSS_CAP_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    MAX_SETTINGS_PER_EDIT,
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_verbs import (
    AcknowledgeLossCapVerb,
    EditBotVerb,
    PauseBotVerb,
    ResumeBotVerb,
    StartBotVerb,
    StopBotVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verbs import BOT_VERBS
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


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(
        **{"bot_id": "44wa1x", "wait": 15.0, "json": True, "format": None, **values}
    )


def _run(
    verb: IBotVerb, host: RecordingHostControl, **values: object
) -> CliOutcome | None:
    dispatcher = BotQueryDispatcher(FakeBotStore(), HeldProbe(True))
    return verb.run(
        _args(**values), verb_world(dispatcher, _PRINTER, host_control=host)
    )


@pytest.mark.parametrize(
    ("verb", "action"),
    [
        (StopBotVerb(), HostControlAction.STOP),
        (PauseBotVerb(), HostControlAction.PAUSE),
        (ResumeBotVerb(), HostControlAction.RESUME),
        (StartBotVerb(), HostControlAction.START),
    ],
)
def test_each_verb_asks_the_host_for_its_action_on_the_named_bot(
    verb: IBotVerb, action: HostControlAction
) -> None:
    host = RecordingHostControl()

    _run(verb, host, wait=3.5)

    assert host.sent == [(HostControlRequest(action, "44wa1x", None), 3.5)]


def test_a_stop_carries_the_close_position_flag_to_the_host() -> None:
    host = RecordingHostControl()

    _run(StopBotVerb(), host, wait=3.5, close_position=True)

    assert host.sent == [
        (
            HostControlRequest(
                HostControlAction.STOP, "44wa1x", None, close_position=True
            ),
            3.5,
        )
    ]


def test_the_verbs_are_registered_under_the_words_the_operator_types() -> None:
    assert {"stop", "pause", "resume", "start", "edit"} <= {
        verb.name for verb in BOT_VERBS
    }


def test_resume_carries_the_venue_the_operator_typed() -> None:
    host = RecordingHostControl()

    _run(ResumeBotVerb(), host, confirm_venue="spot_mainnet")

    assert host.sent[0][0].confirmed_venue == "spot_mainnet"


def test_an_accepted_command_prints_the_hosts_words_as_json_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    host = RecordingHostControl(
        HostControlReply(S.DONE, "the bot is STOPPING", "c" * 32)
    )

    outcome = _run(StopBotVerb(), host)

    document = json.loads(capsys.readouterr().out)
    assert outcome is None
    assert document["schema"] == "sew.bot-control/1"
    assert document["data"] == {
        "action": "stop",
        "bot_id": "44wa1x",
        "status": "done",
        "message": "the bot is STOPPING",
        "command_id": "c" * 32,
    }


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (S.REFUSED, ExitCode.USAGE),
        (S.REJECTED, ExitCode.ERROR),
        (S.NO_CONTROL, ExitCode.CONFIGURATION),
        (S.NOT_RUNNING, ExitCode.HOST_NOT_RUNNING),
        (S.NO_ANSWER, ExitCode.HOST_UNHEALTHY),
    ],
)
def test_every_other_outcome_has_its_own_exit_code_and_says_why(
    status: HostControlStatus, code: ExitCode, capsys: pytest.CaptureFixture[str]
) -> None:
    host = RecordingHostControl(HostControlReply(status, "the words"))

    outcome = _run(StopBotVerb(), host)

    assert isinstance(outcome, CliOutcome)
    assert outcome.code is code
    assert outcome.message == "bot stop 44wa1x: the words"
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("wait", [float("nan"), float("inf"), -2.0])
def test_a_wait_that_is_not_a_finite_number_is_a_usage_error_and_asks_nothing(
    wait: float,
) -> None:
    host = RecordingHostControl()

    outcome = _run(StopBotVerb(), host, wait=wait)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert host.sent == []


def test_start_carries_the_venue_the_operator_typed() -> None:
    host = RecordingHostControl()

    _run(StartBotVerb(), host, confirm_venue="futures_mainnet")

    assert host.sent[0][0] == HostControlRequest(
        HostControlAction.START, "44wa1x", "futures_mainnet"
    )


def test_a_refused_start_exits_two_in_the_screens_words() -> None:
    host = RecordingHostControl(
        HostControlReply(S.REFUSED, "Bot 44wa1x is HALTED: run --resume-halted")
    )

    outcome = _run(StartBotVerb(), host)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert (
        outcome.message == "bot start 44wa1x: Bot 44wa1x is HALTED: run --resume-halted"
    )


# ---- EPIC-038L: bot edit -----------------------------------------------------------------------


def _edit(
    host: RecordingHostControl, *sets: str, **values: object
) -> CliOutcome | None:
    return _run(EditBotVerb(), host, **{"set": list(sets)} | values)


def test_edit_sends_the_settings_in_the_order_typed_and_no_venue() -> None:
    host = RecordingHostControl()

    _edit(host, "lower=81000", "upper=90000", wait=4.0)

    assert host.sent == [
        (
            HostControlRequest(
                HostControlAction.EDIT,
                "44wa1x",
                None,
                settings=(
                    ParameterSetting("lower", "81000"),
                    ParameterSetting("upper", "90000"),
                ),
            ),
            4.0,
        )
    ]


@pytest.mark.parametrize(
    ("given", "says"),
    [
        ([], "at least one --set"),
        (["lower"], "--set 1: it is not key=value"),
        (["lower=81000", "=5"], "--set 2"),
        (["lower="], "--set 1"),
        (["Lower=1"], "--set 1"),
        (["lower=1 2"], "--set 1"),
        (["lower=1", "lower=2"], "lower is given more than once"),
        ([f"p{i}=1" for i in range(MAX_SETTINGS_PER_EDIT + 1)], "at most"),
    ],
)
def test_a_set_that_is_not_sound_is_a_usage_error_and_asks_the_host_nothing(
    given: list[str], says: str
) -> None:
    host = RecordingHostControl()

    outcome = _edit(host, *given)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert says in outcome.message
    assert host.sent == []


def test_a_usage_error_never_repeats_what_was_typed_as_a_value() -> None:
    outcome = _edit(RecordingHostControl(), "lower=sec ret")

    assert isinstance(outcome, CliOutcome)
    assert "sec ret" not in outcome.message


def test_no_set_at_all_is_a_usage_error_even_when_the_parser_gave_none() -> None:
    host = RecordingHostControl()

    outcome = _run(EditBotVerb(), host, set=None)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert host.sent == []


def test_an_accepted_edit_prints_the_hosts_old_to_new_words(
    capsys: pytest.CaptureFixture[str],
) -> None:
    host = RecordingHostControl(
        HostControlReply(S.DONE, "lower 81305 -> 81000. The bot is DRAFT", "c" * 32)
    )

    outcome = _edit(host, "lower=81000")

    document = json.loads(capsys.readouterr().out)
    assert outcome is None
    assert document["data"]["action"] == "edit"
    assert document["data"]["message"].startswith("lower 81305 -> 81000")


def test_a_refused_edit_exits_two_in_the_screens_words() -> None:
    host = RecordingHostControl(
        HostControlReply(
            S.REFUSED, "Bot 44wa1x is RUNNING: only a DRAFT or STOPPED bot"
        )
    )

    outcome = _edit(host, "lower=81000")

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert outcome.message.startswith("bot edit 44wa1x: Bot 44wa1x is RUNNING")


def test_the_shipped_declaration_parses_repeated_sets_in_order() -> None:
    """`--set` is `append` in `cli_commands.json`: the verb receives every one, as a list."""
    path = Path(__file__).resolve().parents[5] / "src/config/cli_commands.json"
    config = Mock(spec=IConfig)
    config.get.return_value = json.loads(path.read_text(encoding="utf-8"))[
        "CLI_COMMANDS"
    ]

    args = build_parser(config).parse_args(
        ["bot", "edit", "44wa1x", "--set", "lower=81000", "--set", "upper=90000"]
    )

    assert (args.command, args.action, args.bot_id) == ("bot", "edit", "44wa1x")
    assert args.set == ["lower=81000", "upper=90000"]
    assert args.wait == 15


def test_the_help_of_edit_tells_the_operator_the_plan_file_is_theirs_to_update() -> (
    None
):
    path = Path(__file__).resolve().parents[5] / "src/config/cli_commands.json"
    edit = json.loads(path.read_text(encoding="utf-8"))["CLI_COMMANDS"]["bot"][
        "subparsers"
    ]["commands"]["edit"]

    assert "plan file" in edit["help"] and "bot apply" in edit["help"]
    assert "NOT updated" in edit["help"]
    assert edit["read_only"] is True


def test_loss_cap_ack_asks_the_host_to_acknowledge_without_naming_a_bot() -> None:
    host = RecordingHostControl()

    _run(AcknowledgeLossCapVerb(), host, wait=2.0, bot_id=None)

    assert host.sent == [
        (
            HostControlRequest(
                HostControlAction.ACKNOWLEDGE_LOSS_CAP, LOSS_CAP_SUBJECT
            ),
            2.0,
        )
    ]


def test_loss_cap_ack_is_a_verb_the_operator_can_type() -> None:
    assert "loss-cap-ack" in {verb.name for verb in BOT_VERBS}
