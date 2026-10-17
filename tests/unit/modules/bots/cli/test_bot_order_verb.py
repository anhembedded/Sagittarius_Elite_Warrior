"""`bot order <id>` prints the orders a bot's file records, read-only (`BOT-187`)."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_order_reports import (
    NO_HOST_NOTE,
    STORED_NOTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_order_verbs import OrderBotVerb
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    LevelOrder,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
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
_PAYLOAD_KEYS = {
    "source", "app_running", "bot_id", "name", "symbol", "state",
    "orders_known", "orders", "unreadable",
}  # fmt: skip
_ORDER_KEYS = {
    "level", "side", "price", "quantity", "executed", "state", "client_order_id",
}  # fmt: skip


def _runtime() -> dict[str, object]:
    ladder = GridRuntime(
        (
            RuntimeLevel(0, Decimal(100), Decimal(1)),
            RuntimeLevel(
                1,
                Decimal(110),
                Decimal(1),
                LevelState.RESTING,
                LevelOrder("sew-aaa-1", OrderSide.BUY, Decimal(110), Decimal("0.5")),
            ),
            RuntimeLevel(
                2,
                Decimal(120),
                Decimal(1),
                LevelState.PARTIAL,
                LevelOrder(
                    "sew-aaa-2",
                    OrderSide.SELL,
                    Decimal(120),
                    Decimal("0.5"),
                    executed=Decimal("0.2"),
                ),
            ),
        )
    )
    return dict(encode_runtime(ladder))


def _world(held: bool = True) -> BotQueryDispatcher:
    store = FakeBotStore()
    seed(store, "aaaaaa", BotLifecycleState.RUNNING, runtime=_runtime())
    seed(store, "bbbbbb", BotLifecycleState.STOPPED, runtime={})
    seed(store, "cccccc", BotLifecycleState.RUNNING, runtime={"levels": "not a list"})
    store.refuse_file(BotId("dddddd"), "not valid JSON")
    return BotQueryDispatcher(store, HeldProbe(held))


def _run(
    capsys: pytest.CaptureFixture[str],
    bot_id: str,
    *,
    json_out: bool = True,
    held: bool = True,
) -> tuple[object, str]:
    args = argparse.Namespace(bot_id=bot_id, json=json_out, format=None)
    outcome = OrderBotVerb().run(args, verb_world(_world(held), _PRINTER))
    return outcome, capsys.readouterr().out


def test_the_orders_are_the_ones_the_file_records_with_their_stored_state(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome, out = _run(capsys, "aaaaaa")

    document = json.loads(out)
    assert outcome is None
    assert document["schema"] == "sew.bot-order/1"
    data = document["data"]
    assert data["source"] == "stored"
    assert data["orders"] == [
        {
            "level": 1,
            "side": "BUY",
            "price": "110",
            "quantity": "0.5",
            "executed": "0",
            "state": "RESTING",
            "client_order_id": "sew-aaa-1",
        },
        {
            "level": 2,
            "side": "SELL",
            "price": "120",
            "quantity": "0.5",
            "executed": "0.2",
            "state": "PARTIAL",
            "client_order_id": "sew-aaa-2",
        },
    ]


def test_the_bot_order_payload_keys_are_pinned(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out = _run(capsys, "aaaaaa")

    data = json.loads(out)["data"]
    assert set(data) == _PAYLOAD_KEYS
    assert all(set(order) == _ORDER_KEYS for order in data["orders"])


def test_the_text_view_says_stored_and_lists_one_row_per_order(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out = _run(capsys, "aaaaaa", json_out=False)

    assert STORED_NOTE in out
    assert NO_HOST_NOTE not in out
    rows = [line for line in out.splitlines() if "sew-aaa-" in line]
    assert [row.split()[:2] for row in rows] == [["1", "BUY"], ["2", "SELL"]]
    assert "PARTIAL" in rows[1]


def test_with_no_copy_running_the_text_and_json_say_the_file_may_be_behind(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, text = _run(capsys, "aaaaaa", json_out=False, held=False)
    _, out = _run(capsys, "aaaaaa", held=False)

    assert NO_HOST_NOTE in text
    assert json.loads(out)["data"]["app_running"] is False


def test_a_bot_at_rest_with_no_run_prints_no_orders(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome, text = _run(capsys, "bbbbbb", json_out=False)
    _, out = _run(capsys, "bbbbbb")

    assert outcome is None
    assert "No orders." in text
    data = json.loads(out)["data"]
    assert (data["orders"], data["orders_known"]) == ([], True)


def test_a_running_bot_whose_runtime_cannot_be_read_does_not_claim_no_orders(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, text = _run(capsys, "cccccc", json_out=False)
    _, out = _run(capsys, "cccccc")

    assert "No orders." not in text
    assert "Orders unknown" in text
    assert json.loads(out)["data"]["orders_known"] is False


def test_an_unreadable_bot_file_is_reported_with_its_path_not_crashed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome, text = _run(capsys, "dddddd", json_out=False)
    _, out = _run(capsys, "dddddd")

    assert outcome is None
    assert str(BOTS_DIRECTORY / "dddddd.json") in text
    assert "not valid JSON" in text
    data = json.loads(out)["data"]
    assert data["unreadable"] == {
        "path": str(BOTS_DIRECTORY / "dddddd.json"),
        "reason": "not valid JSON",
    }
    assert data["orders_known"] is False


def test_an_unknown_id_is_refused_in_words(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome, out = _run(capsys, "zzzzzz")

    assert out == ""
    assert getattr(outcome, "code", None) is ExitCode.USAGE
    assert "zzzzzz" in getattr(outcome, "message", "")


def test_the_verb_changes_no_bot() -> None:
    store = FakeBotStore()
    seed(store, "aaaaaa", BotLifecycleState.RUNNING, runtime=_runtime())
    before = store.load(BotId("aaaaaa"))

    OrderBotVerb().run(
        argparse.Namespace(bot_id="aaaaaa", json=True, format=None),
        verb_world(BotQueryDispatcher(store, HeldProbe(True)), _PRINTER),
    )

    after = store.load(BotId("aaaaaa"))
    assert isinstance(after, StoredBot)
    assert (after.bot.state, after.runtime) == (before.bot.state, before.runtime)
