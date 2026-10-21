"""`EPIC-045` - `bot add` and `bot delete` ask the running host and speak its answer."""

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
    ADD_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_verbs import (
    AddBotVerb,
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


# ---- EPIC-045: bot add and bot delete ----------------------------------------------------------

_PLAN_ENTRY = {
    "name": "sol grid",
    "kind": "grid",
    "venue": "spot_testnet",
    "symbol": "solusdt",
    "params": {"lower": "80", "upper": "120"},
    "desired_state": "running",
}


def _plan(tmp_path: Path, *bots: dict[str, object]) -> str:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps({"schema": "sew.bot-plan/1", "bots": list(bots)}), encoding="utf-8"
    )
    return str(path)


def _add(host: RecordingHostControl, plan: str, **values: object) -> CliOutcome | None:
    return _run(
        AddBotVerb(),
        host,
        **{"plan": plan, "name": None, "venue": None, "bot_id": None} | values,
    )


def test_add_sends_the_one_entry_of_the_plan_and_names_no_bot_nor_venue(
    tmp_path: Path,
) -> None:
    host = RecordingHostControl()

    _add(host, _plan(tmp_path, _PLAN_ENTRY), wait=3.0)

    assert host.sent == [
        (
            HostControlRequest(
                HostControlAction.ADD,
                ADD_SUBJECT,
                entry=NewBotEntry(
                    "sol grid",
                    "grid",
                    "spot_testnet",
                    "SOLUSDT",
                    (ParameterSetting("lower", "80"), ParameterSetting("upper", "120")),
                ),
            ),
            3.0,
        )
    ]


def test_add_does_not_carry_the_plans_desired_state_to_the_host(tmp_path: Path) -> None:
    host = RecordingHostControl()

    _add(host, _plan(tmp_path, _PLAN_ENTRY))

    request = host.sent[0][0]
    assert request.confirmed_venue is None
    assert "running" not in repr(request)


def test_add_picks_the_named_entry_of_a_plan_of_several(tmp_path: Path) -> None:
    host = RecordingHostControl()
    other = {**_PLAN_ENTRY, "name": "btc grid", "symbol": "BTCUSDT"}

    _add(host, _plan(tmp_path, _PLAN_ENTRY, other), name="btc grid")

    entry = host.sent[0][0].entry
    assert entry is not None and (entry.name, entry.symbol) == ("btc grid", "BTCUSDT")


def test_add_picks_by_venue_a_name_the_plan_holds_twice(tmp_path: Path) -> None:
    host = RecordingHostControl()
    twin = {**_PLAN_ENTRY, "venue": "spot_mainnet"}
    plan = _plan(tmp_path, _PLAN_ENTRY, twin)

    ambiguous = _add(host, plan, name="sol grid")
    _add(host, plan, name="sol grid", venue="spot_mainnet")

    assert isinstance(ambiguous, CliOutcome) and ambiguous.code is ExitCode.USAGE
    assert "--venue" in ambiguous.message
    assert len(host.sent) == 1
    entry = host.sent[0][0].entry
    assert entry is not None and entry.venue == "spot_mainnet"


def test_add_of_a_plan_of_several_without_a_name_lists_them_and_sends_nothing(
    tmp_path: Path,
) -> None:
    host = RecordingHostControl()
    other = {**_PLAN_ENTRY, "name": "btc grid"}

    outcome = _add(host, _plan(tmp_path, _PLAN_ENTRY, other))

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert "sol grid" in outcome.message and "btc grid" in outcome.message
    assert host.sent == []


def test_add_of_a_name_the_plan_does_not_hold_sends_nothing(tmp_path: Path) -> None:
    host = RecordingHostControl()

    outcome = _add(host, _plan(tmp_path, _PLAN_ENTRY), name="eth grid")

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert host.sent == []


@pytest.mark.parametrize(
    "entry",
    [
        {**_PLAN_ENTRY, "name": "sol (grid)"},
        {**_PLAN_ENTRY, "symbol": "SOL/USDT"},
        {**_PLAN_ENTRY, "params": {"lower": "8 0"}},
        {**_PLAN_ENTRY, "kind": "martingale"},
    ],
    ids=["name-bracket", "symbol-slash", "param-space", "unknown-kind"],
)
def test_add_refuses_an_entry_that_cannot_cross_the_command_file_and_sends_nothing(
    tmp_path: Path, entry: dict[str, object]
) -> None:
    host = RecordingHostControl()

    outcome = _add(host, _plan(tmp_path, entry))

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert host.sent == []


def test_add_of_a_file_that_is_not_there_or_not_a_plan_is_a_usage_error(
    tmp_path: Path,
) -> None:
    host = RecordingHostControl()
    garbage = tmp_path / "garbage.json"
    garbage.write_text("not json", encoding="utf-8")

    missing = _add(host, str(tmp_path / "nope.json"))
    bad = _add(host, str(garbage))

    assert isinstance(missing, CliOutcome) and missing.code is ExitCode.USAGE
    assert isinstance(bad, CliOutcome) and bad.code is ExitCode.USAGE
    assert host.sent == []


def test_a_refused_add_exits_two_in_the_hosts_words(tmp_path: Path) -> None:
    host = RecordingHostControl(
        HostControlReply(S.REFUSED, "bot x03yij already has the name 'sol grid'")
    )

    outcome = _add(host, _plan(tmp_path, _PLAN_ENTRY))

    assert isinstance(outcome, CliOutcome) and outcome.code is ExitCode.USAGE
    assert outcome.message.startswith(f"bot add {ADD_SUBJECT}: bot x03yij already has")


def test_an_accepted_add_prints_the_hosts_sentence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = RecordingHostControl(
        HostControlReply(S.DONE, "bot x03yij was created", "c" * 32)
    )

    outcome = _add(host, _plan(tmp_path, _PLAN_ENTRY))

    document = json.loads(capsys.readouterr().out)
    assert outcome is None
    assert document["data"]["action"] == "add"
    assert document["data"]["message"] == "bot x03yij was created"


def _declared(verb: str) -> dict[str, object]:
    path = Path(__file__).resolve().parents[5] / "src/config/cli_commands.json"
    return json.loads(path.read_text(encoding="utf-8"))["CLI_COMMANDS"]["bot"][
        "subparsers"
    ]["commands"][verb]


def test_the_shipped_declaration_parses_add_and_delete() -> None:
    path = Path(__file__).resolve().parents[5] / "src/config/cli_commands.json"
    config = Mock(spec=IConfig)
    config.get.return_value = json.loads(path.read_text(encoding="utf-8"))[
        "CLI_COMMANDS"
    ]
    parser = build_parser(config)

    added = parser.parse_args(["bot", "add", "plan.json", "--name", "sol grid"])
    deleted = parser.parse_args(["bot", "delete", "44wa1x"])

    assert (added.action, added.plan, added.name, added.venue) == (
        "add",
        "plan.json",
        "sol grid",
        None,
    )
    assert (deleted.action, deleted.bot_id, deleted.wait) == ("delete", "44wa1x", 15)


@pytest.mark.parametrize("verb", ["add", "delete"])
def test_add_and_delete_are_read_only_commands_that_talk_to_the_host(verb: str) -> None:
    declared = _declared(verb)

    assert declared["read_only"] is True
    assert declared["modules"] == ["bots", "operations"]


def test_the_help_of_delete_says_nothing_is_sent_to_the_exchange_and_the_plan_is_the_owners() -> (
    None
):
    help_text = str(_declared("delete")["help"])

    assert "sends nothing to the exchange" in help_text
    assert "plan file is not changed" in help_text
