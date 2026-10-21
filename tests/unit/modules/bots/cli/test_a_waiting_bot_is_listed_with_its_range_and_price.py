"""`EPIC-044C` - `bot list` and `bot show` say a bot is waiting, for which range and at which price.

The words are the Plan's (`waiting_text`); a list has no column for them, so they take the reason's
place, and `bot show` has the ladder's position rows below. A bot with a reason of its own keeps it.
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verbs import (
    ListBotsVerb,
    ShowBotVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.status_world import (
    BotQueryDispatcher,
    HeldProbe,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.verb_world import verb_world

_PRINTER = ReportPrinter(ReportFormats.default())
_CONFIG = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "off",
    "take_profit": "off",
}
_SENTENCE = (
    "Waiting for the price to enter 60,000.00–70,000.00 (now 58,000.00); "
    "nothing is placed until it does"
)


def _waiting_run(price: Decimal | None) -> dict[str, object]:
    runtime = GridRuntime(
        (),
        mark_price=price,
        mark_price_at=None
        if price is None
        else FAKE_CLOCK_START - timedelta(seconds=7),
    )
    return dict(encode_runtime(runtime))


def _world() -> BotQueryDispatcher:
    store = FakeBotStore()
    seed(store, "wait01", S.AWAITING_RANGE, _CONFIG, _waiting_run(Decimal(58000)))
    seed(store, "wait02", S.AWAITING_RANGE, _CONFIG, _waiting_run(None))
    seed(store, "halt01", S.HALTED, _CONFIG, _waiting_run(Decimal(58000)))
    return BotQueryDispatcher(store, HeldProbe(False))


def _text(verb: ListBotsVerb | ShowBotVerb, capsys: pytest.CaptureFixture[str], **a):
    args = argparse.Namespace(json=False, format=None, **a)
    verb.run(args, verb_world(_world(), _PRINTER))
    return capsys.readouterr().out


def test_bot_list_names_the_state_the_range_and_the_price(
    capsys: pytest.CaptureFixture[str],
) -> None:
    line = next(
        row
        for row in _text(ListBotsVerb(), capsys).splitlines()
        if row.startswith("wait01")
    )

    assert "AWAITING_RANGE" in line
    assert _SENTENCE in line


def test_bot_show_prints_the_sentence_and_the_last_price_heard(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="wait01")

    reason = next(row for row in out.splitlines() if row.startswith("Reason"))
    assert _SENTENCE in reason
    last = next(row for row in out.splitlines() if row.startswith("Last price heard"))
    assert "58,000.00" in last


def test_a_waiting_bot_that_heard_no_price_says_so(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="wait02")

    assert "(no price heard yet)" in out


def test_a_bot_that_is_not_waiting_prints_its_own_reason_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ListBotsVerb(), capsys)

    halted = next(row for row in out.splitlines() if row.startswith("halt01"))
    assert "Waiting for the price" not in halted


def test_the_json_reason_is_unchanged_for_a_waiting_bot(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = argparse.Namespace(json=True, format=None)
    ListBotsVerb().run(args, verb_world(_world(), _PRINTER))

    bots = json.loads(capsys.readouterr().out)["data"]["bots"]

    waiting = next(bot for bot in bots if bot["bot_id"] == "wait01")
    assert waiting["state"] == "AWAITING_RANGE"
    assert waiting["reason"] == ""
