"""`bot list` and `bot show` print the read model the Bots tab's queries give (`EPIC-038C`)."""

from __future__ import annotations

import argparse
import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verbs import (
    BOT_VERBS,
    IBotVerb,
    ListBotsVerb,
    ShowBotVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    RECORDED_STATES_NOTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.status_world import (
    BOTS_DIRECTORY,
    BotQueryDispatcher,
    HeldProbe,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.verb_world import verb_world

_PRINTER = ReportPrinter(ReportFormats.default())
_LIST_KEYS = {"app_running", "bots", "unreadable", "counts"}
_BOT_KEYS = {
    "bot_id", "name", "kind", "venue", "symbol", "state", "reason",
    "run_started_at", "health", "resting_orders", "recovers_on_restart",
    "reason_detail", "recovery", "parameters", "earnings", "ladder",
}  # fmt: skip
_UNREADABLE_KEYS = {"bot_id", "state", "path", "reason"}


def _world(held: bool = True) -> BotQueryDispatcher:
    store = FakeBotStore()
    seed(store, "aaaaaa", BotLifecycleState.RUNNING)
    seed(store, "bbbbbb", BotLifecycleState.HALTED)
    store.refuse_file(BotId("dddddd"), "not valid JSON")
    return BotQueryDispatcher(store, HeldProbe(held))


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**{"json": True, "format": None, **values})


def _run(
    verb: IBotVerb, capsys: pytest.CaptureFixture[str], **values: object
) -> tuple[object, str]:
    outcome = verb.run(_args(**values), verb_world(_world(), _PRINTER))
    return outcome, capsys.readouterr().out


def test_bot_list_json_agrees_with_the_bots_tab_list_on_every_bot(
    capsys: pytest.CaptureFixture[str],
) -> None:
    dispatcher = _world()
    screen = dispatcher.dispatch(ListBotsQuery, ListBotsQuery())
    assert isinstance(screen, BotList)

    outcome = ListBotsVerb().run(_args(), verb_world(dispatcher, _PRINTER))

    document = json.loads(capsys.readouterr().out)
    assert outcome is None
    assert document["schema"] == "sew.bot-list/1"
    shown = [
        (b["bot_id"], b["name"], b["kind"], b["venue"], b["symbol"], b["state"])
        for b in document["data"]["bots"]
    ]
    assert shown == [
        (b.bot_id, b.name, b.kind, b.venue.value, b.symbol, b.state.value)
        for b in screen.bots
    ]
    assert [u["bot_id"] for u in document["data"]["unreadable"]] == [
        _stem(r.name) for r in screen.refused
    ]


def _stem(name: str) -> str:
    return name.removesuffix(".json")


def test_the_bot_report_payload_keys_are_pinned(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out = _run(ListBotsVerb(), capsys)

    data = json.loads(out)["data"]
    assert set(data) == _LIST_KEYS
    assert all(set(bot) == _BOT_KEYS for bot in data["bots"])
    assert all(set(bot) == _UNREADABLE_KEYS for bot in data["unreadable"])


def test_an_unreadable_file_is_shown_with_its_path_in_the_text_view(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out = _run(ListBotsVerb(), capsys, json=False)

    line = next(row for row in out.splitlines() if row.startswith("dddddd"))
    assert "unreadable" in line
    assert str(BOTS_DIRECTORY / "dddddd.json") in line


def test_bot_show_prints_one_bot(capsys: pytest.CaptureFixture[str]) -> None:
    outcome, out = _run(ShowBotVerb(), capsys, bot_id="bbbbbb")

    document = json.loads(out)
    assert outcome is None
    assert document["schema"] == "sew.bot-show/1"
    assert [b["bot_id"] for b in document["data"]["bots"]] == ["bbbbbb"]


def test_bot_show_text_prints_the_recovery_table_and_json_carries_the_same_rows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`EPIC-042G`: the text and the JSON of one bot hold the same reasons."""
    _, text = _run(ShowBotVerb(), capsys, bot_id="bbbbbb", json=False)
    _, out = _run(ShowBotVerb(), capsys, bot_id="bbbbbb")

    rules = json.loads(out)["data"]["bots"][0]["recovery"]["rules"]
    rows = [line for line in text.splitlines() if line.startswith("Recovery")]
    assert [rule["code"] for rule in rules] == ["price_feed_stale", "user_stream_down"]
    assert len(rows) == len(rules)
    assert all(rule["code"] in row for rule, row in zip(rules, rows, strict=True))
    assert "after 2 min clear, 0 of 3 used in 24 h" in rows[0]


def test_an_unknown_id_exits_two_with_a_plain_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome, out = _run(ShowBotVerb(), capsys, bot_id="zzzzzz")

    assert out == ""
    assert getattr(outcome, "code", None) is ExitCode.USAGE
    assert "zzzzzz" in getattr(outcome, "message", "")


def test_the_verbs_are_a_table_not_a_chain() -> None:
    assert [verb.name for verb in BOT_VERBS] == [
        "list",
        "show",
        "order",
        "apply",
        "export",
        "stop",
        "pause",
        "resume",
        "start",
        "edit",
    ]


def test_with_no_copy_running_the_text_says_the_states_are_only_recorded(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ListBotsVerb().run(_args(json=False), verb_world(_world(held=False), _PRINTER))

    out = capsys.readouterr().out
    assert RECORDED_STATES_NOTE in out
    assert out.index(RECORDED_STATES_NOTE) < out.index("aaaaaa")


def test_with_no_copy_running_the_json_carries_the_same_fact(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ShowBotVerb().run(_args(bot_id="aaaaaa"), verb_world(_world(held=False), _PRINTER))

    assert json.loads(capsys.readouterr().out)["data"]["app_running"] is False


def test_with_a_copy_running_the_states_are_not_qualified(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ListBotsVerb().run(_args(json=False), verb_world(_world(held=True), _PRINTER))

    assert RECORDED_STATES_NOTE not in capsys.readouterr().out
