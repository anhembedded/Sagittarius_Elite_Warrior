"""`bot stop`, `bot pause` and `bot resume` ask the running host and speak its answer (`EPIC-038J`)."""

from __future__ import annotations

import argparse
import json

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
    DeleteBotVerb,
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
        (DeleteBotVerb(), HostControlAction.DELETE),
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
    assert {"stop", "pause", "resume", "start", "delete"} <= {
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


def test_delete_asks_for_no_venue_and_no_close() -> None:
    host = RecordingHostControl()

    _run(DeleteBotVerb(), host)

    assert host.sent[0][0] == HostControlRequest(HostControlAction.DELETE, "44wa1x")


def test_a_refused_start_exits_two_in_the_screens_words() -> None:
    host = RecordingHostControl(
        HostControlReply(S.REFUSED, "Bot 44wa1x is HALTED: run --resume-halted")
    )

    outcome = _run(StartBotVerb(), host)

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert (
        outcome.message == "bot start 44wa1x: Bot 44wa1x is HALTED: run --resume-halted"
    )
