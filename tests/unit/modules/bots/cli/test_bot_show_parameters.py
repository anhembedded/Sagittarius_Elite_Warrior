"""`EPIC-038L` - `bot show <id> --params` prints every parameter a bot stores, so an operator reads them
before `bot edit`, from the read-only copy and with no host round trip."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verbs import (
    ListBotsVerb,
    ShowBotVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_parameter_check import (
    grid_parameter_problem,
)
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.status_world import (
    BotQueryDispatcher,
    HeldProbe,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.verb_world import verb_world

_PRINTER = ReportPrinter(ReportFormats.default())
_SPOT = {
    "lower": "81305.10",
    "upper": "90000",
    "grid_count": "12",
    "spacing": "GEOMETRIC",
    "capital_quote": "200.50",
    "stop_loss": "percent:5",
    "take_profit": "off",
}
_FUTURES = {**_SPOT, "direction": "SHORT", "leverage": "3", "on_range_exit": "close"}


def _show(
    capsys: pytest.CaptureFixture[str], bot_id: str, **values: object
) -> tuple[object, str]:
    store = FakeBotStore()
    seed(store, "spotbt", BotLifecycleState.STOPPED, dict(_SPOT))
    seed(
        store,
        "futbot",
        BotLifecycleState.STOPPED,
        dict(_FUTURES),
        venue=TradingVenue.FUTURES_TESTNET,
    )
    empty = seed(store, "empty1", BotLifecycleState.DRAFT)
    store.save(
        StoredBot(replace(empty, definition=replace(empty.definition, config={})), {})
    )
    store.refuse_file(BotId("badbot"), "not valid JSON")
    args = argparse.Namespace(
        **{"bot_id": bot_id, "json": True, "format": None, **values}
    )
    # A read-only copy beside a host: no lock, no command file.
    outcome = ShowBotVerb().run(
        args, verb_world(BotQueryDispatcher(store, HeldProbe(True)), _PRINTER)
    )
    return outcome, capsys.readouterr().out


@pytest.mark.parametrize(
    ("bot_id", "stored"), [("spotbt", _SPOT), ("futbot", _FUTURES)]
)
def test_the_json_lists_every_stored_parameter_sorted_and_exactly_as_stored(
    capsys: pytest.CaptureFixture[str], bot_id: str, stored: dict[str, str]
) -> None:
    outcome, out = _show(capsys, bot_id)

    parameters = json.loads(out)["data"]["bots"][0]["parameters"]
    assert outcome is None
    assert parameters == stored
    assert list(parameters) == sorted(stored)
    assert parameters["lower"] == "81305.10", "no rounding, no reformatting"


@pytest.mark.parametrize(
    ("bot_id", "stored"), [("spotbt", _SPOT), ("futbot", _FUTURES)]
)
def test_the_text_with_params_has_one_row_per_key_sorted_by_key(
    capsys: pytest.CaptureFixture[str], bot_id: str, stored: dict[str, str]
) -> None:
    _, out = _show(capsys, bot_id, json=False, params=True)

    rows = [
        line.split(None, 2) for line in out.splitlines() if line.startswith("param ")
    ]
    assert [(row[1], row[2]) for row in rows] == sorted(stored.items())


def test_the_text_without_params_prints_no_parameter_row_and_the_json_still_carries_them(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, text = _show(capsys, "spotbt", json=False)
    _, out = _show(capsys, "spotbt")

    assert "param " not in text and "81305.10" not in text
    assert json.loads(out)["data"]["bots"][0]["parameters"] == _SPOT


def test_a_bot_with_no_parameters_says_none_set(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out = _show(capsys, "empty1", json=False, params=True)

    assert "none set" in out


def test_an_unreadable_bot_file_is_reported_not_crashed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome, out = _show(capsys, "badbot", json=False, params=True)

    assert outcome is None
    assert "badbot" in out and "not valid JSON" in out


@pytest.mark.parametrize("bot_id", ["spotbt", "futbot"])
def test_the_listed_keys_are_the_ones_bot_edit_accepts(
    capsys: pytest.CaptureFixture[str], bot_id: str
) -> None:
    _, out = _show(capsys, bot_id)

    parameters = json.loads(out)["data"]["bots"][0]["parameters"]
    assert grid_parameter_problem(parameters, parameters.keys()) is None


def test_a_listing_carries_no_parameters_so_it_stays_small(
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = FakeBotStore()
    seed(store, "spotbt", BotLifecycleState.STOPPED, dict(_SPOT))
    ListBotsVerb().run(
        argparse.Namespace(json=True, format=None),
        verb_world(BotQueryDispatcher(store, HeldProbe(True)), _PRINTER),
    )

    assert json.loads(capsys.readouterr().out)["data"]["bots"][0]["parameters"] is None
