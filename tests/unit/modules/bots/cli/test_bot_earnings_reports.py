"""`BOT-192` - `bot list` and `bot show` print the run's profit, cycles and total PnL.

@details The figures and the words are the Bots tab's (`bot_facts`), read from the stored bot record
with no exchange and no host. A figure the record cannot give is the tab's no-value text, never a
zero: `—` with no run account, `no price yet` while the total waits for a price.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verbs import (
    ListBotsVerb,
    ShowBotVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.status_world import (
    BotQueryDispatcher,
    HeldProbe,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.verb_world import verb_world

S = BotLifecycleState
_PRINTER = ReportPrinter(ReportFormats.default())
_NOW = datetime(2026, 10, 19, tzinfo=UTC)
#: Nothing held, so the total is the realised total and needs no price.
_EARNED = replace(
    GridRuntime(()),
    realised_profit=Decimal("1234.5"),
    realised_total=Decimal("1230.25"),
    completed_cycles=7,
)
#: Base held and no price heard: the total cannot be judged.
_UNPRICED = replace(
    _EARNED,
    inventory=Decimal("0.01"),
    cost=Decimal(640),
    realised_profit=Decimal("5.74"),
    completed_cycles=1,
)


def _world() -> BotQueryDispatcher:
    store = FakeBotStore()
    seed(store, "aaaaaa", S.STOPPED, runtime=encode_runtime(_EARNED))
    seed(store, "bbbbbb", S.RUNNING, runtime=encode_runtime(_UNPRICED))
    seed(store, "cccccc", S.DRAFT, runtime={})
    return BotQueryDispatcher(store, HeldProbe(False))


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**{"json": True, "format": None, **values})


def _json(verb: ListBotsVerb | ShowBotVerb, capsys: pytest.CaptureFixture[str], **a):
    verb.run(_args(**a), verb_world(_world(), _PRINTER))
    return json.loads(capsys.readouterr().out)["data"]["bots"]


def _text(verb: ListBotsVerb | ShowBotVerb, capsys: pytest.CaptureFixture[str], **a):
    verb.run(_args(json=False, **a), verb_world(_world(), _PRINTER))
    return capsys.readouterr().out


def _tab(bot_id: str):
    snapshot = _world().dispatch(GetBotQuery, GetBotQuery(bot_id))
    assert isinstance(snapshot, BotSnapshot)
    return bot_facts(snapshot, _NOW)


def test_bot_show_prints_the_figures_the_bots_tab_shows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="aaaaaa")

    tab = _tab("aaaaaa")
    assert (tab.grid_profit, tab.total_pnl) == ("1,234.50", "1,230.25")
    assert f"Grid profit  {tab.grid_profit}" in out
    assert f"Total PnL    {tab.total_pnl}" in out
    assert "Cycles       7" in out
    assert f"Unrealised   {tab.unrealised}" in out
    assert out.index("Grid profit") < out.index("Cycles") < out.index("Total PnL")
    assert out.index("Total PnL") < out.index("Unrealised")


def test_a_total_that_waits_for_a_price_says_so_and_is_not_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="bbbbbb")
    [bot] = _json(ShowBotVerb(), capsys, bot_id="bbbbbb")

    assert _tab("bbbbbb").total_pnl == "no price yet"
    assert "Total PnL    no price yet" in out
    assert "Unrealised   no price yet" in out
    assert _tab("bbbbbb").unrealised == "no price yet"
    assert bot["earnings"] == {
        "grid_profit": "5.74",
        "completed_cycles": 1,
        "total_pnl": None,
        "unpriced_fees": 0,
        "holds_base": True,
        "unrealised": None,
        "mark_price": None,
    }


def test_a_bot_with_no_run_account_shows_the_no_value_text_not_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="cccccc")
    [bot] = _json(ShowBotVerb(), capsys, bot_id="cccccc")

    assert _tab("cccccc").grid_profit == "—"
    assert "Grid profit  —" in out and "Cycles       —" in out
    assert "Total PnL    —" in out
    assert bot["earnings"] is None


def test_bot_list_has_a_column_for_each_figure_and_json_carries_exact_decimals(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ListBotsVerb(), capsys)
    bots = {bot["bot_id"]: bot for bot in _json(ListBotsVerb(), capsys)}

    head = next(line for line in out.splitlines() if line.startswith("ID"))
    assert all(word in head for word in ("GRID PROFIT", "CYCLES", "TOTAL PNL"))
    row = next(line for line in out.splitlines() if line.startswith("aaaaaa"))
    assert "1,234.50" in row and "1,230.25" in row
    assert bots["aaaaaa"]["earnings"] == {
        "grid_profit": "1234.5",
        "completed_cycles": 7,
        "total_pnl": "1230.25",
        "unpriced_fees": 0,
        "holds_base": False,
        "unrealised": "0",
        "mark_price": None,
    }
