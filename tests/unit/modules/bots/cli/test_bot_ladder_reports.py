"""`BOT-193` - `bot show` and `bot list` print a Grid bot's ladder as the Bots tab shows it.

@details The figures and the words are the Bots tab's (`ladder_facts`), read from the stored bot
record with no exchange and no host. `--grids` adds one row per grid; a figure the record cannot
give is the no-value text in the text view and `null` in the JSON, never zero; the bot's current
saved parameters make the ladder.
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    grid_ladder_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder_texts import (
    FEE_NOT_SAVED,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_ladder_facts import (
    ladder_facts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
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
_CONFIG = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "percent:5",
    "take_profit": "off",
}


def _run(*resting: tuple[int, OrderSide, str]) -> dict[str, object]:
    orders = {level: (side, Decimal(price)) for level, side, price in resting}
    levels = tuple(
        RuntimeLevel(
            index,
            Decimal(60000 + 1000 * index),
            Decimal("0.01"),
            LevelState.RESTING if index in orders else LevelState.EMPTY,
            LevelOrder(f"c{index}", orders[index][0], orders[index][1], Decimal(1))
            if index in orders
            else None,
        )
        for index in range(11)
    )
    runtime = GridRuntime(
        levels,
        realised_profit=Decimal(30),
        completed_cycles=6,
        mark_price=Decimal(64500),
        mark_price_at=FAKE_CLOCK_START - timedelta(minutes=5),
    )
    return dict(encode_runtime(runtime))


def _world() -> BotQueryDispatcher:
    store = FakeBotStore()
    seed(
        store,
        "aaaaaa",
        S.RUNNING,
        _CONFIG,
        _run((4, OrderSide.BUY, "64000"), (6, OrderSide.SELL, "66000")),
    )
    seed(store, "cccccc", S.DRAFT, {"lower": "60000"}, {})
    return BotQueryDispatcher(store, HeldProbe(False))


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**{"json": True, "format": None, **values})


def _text(verb: ListBotsVerb | ShowBotVerb, capsys: pytest.CaptureFixture[str], **a):
    verb.run(_args(json=False, **a), verb_world(_world(), _PRINTER))
    return capsys.readouterr().out


def _json(verb: ListBotsVerb | ShowBotVerb, capsys: pytest.CaptureFixture[str], **a):
    verb.run(_args(**a), verb_world(_world(), _PRINTER))
    return json.loads(capsys.readouterr().out)["data"]["bots"]


def _tab_rows(bot_id: str) -> dict[str, str]:
    snapshot = _world().dispatch(GetBotQuery, GetBotQuery(bot_id))
    assert isinstance(snapshot, BotSnapshot)
    return dict(ladder_facts(grid_ladder_of(snapshot, FAKE_CLOCK_START)).rows)


def test_bot_show_prints_the_position_rows_the_bots_tab_shows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="aaaaaa")

    tab = _tab_rows("aaaaaa")
    assert tab["last_price"] == "64,500.00, 5 min ago"
    for label, key in (
        ("Last price", "last_price"),
        ("Lower edge", "lower_edge"),
        ("Upper edge", "upper_edge"),
        ("Stop loss", "stop_loss"),
        ("Take profit", "take_profit"),
        ("Per cycle", "cycle_average"),
    ):
        assert f"{label:<12} {tab[key]}" in out, label
    assert tab["lower_edge"] == "60,000.00 (-6.98%)"


def test_bot_show_prints_the_summary_line_with_its_reasons(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="aaaaaa")

    line = next(row for row in out.splitlines() if row.startswith("Ladder"))
    assert (
        "Arithmetic spacing: steps from 1.45% at the top to 1.67% at the bottom" in line
    )
    assert FEE_NOT_SAVED in line


def test_grids_prints_one_row_per_grid_with_the_state_the_run_records(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="aaaaaa", grids=True)

    lines = out.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Grids of bot"))
    head, *rows = lines[start + 1 : start + 12]
    assert all(word in head for word in ("BUY", "SELL", "STEP", "NET STEP", "NOW"))
    assert len(rows) == 10
    assert rows[0].split()[:3] == ["60,000.00", "61,000.00", "1.67%"]
    assert rows[4].rstrip().endswith("waiting to buy")
    assert rows[5].rstrip().endswith("waiting to sell")
    assert rows[0].rstrip().endswith("no order")
    assert "—" in rows[0]
    assert "Net figures are blank" in out
    assert "estimate" in out


def test_without_grids_the_grid_table_is_not_printed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert "Grids of bot" not in _text(ShowBotVerb(), capsys, bot_id="aaaaaa")


def test_grids_and_params_print_both(capsys: pytest.CaptureFixture[str]) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="aaaaaa", grids=True, params=True)

    assert "param lower" in out and "Grids of bot aaaaaa" in out


def test_a_bot_whose_parameters_make_no_ladder_says_why(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ShowBotVerb(), capsys, bot_id="cccccc", grids=True)
    [bot] = _json(ShowBotVerb(), capsys, bot_id="cccccc")

    assert "upper is missing" in out
    assert bot["ladder"]["available"] is False
    assert "upper is missing" in bot["ladder"]["reason"]
    assert "Grids of bot cccccc" in out


def test_the_json_carries_the_ladder_as_exact_text_and_null_where_unknown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    [bot] = _json(ShowBotVerb(), capsys, bot_id="aaaaaa")

    ladder = bot["ladder"]
    assert ladder["available"] is True
    assert ladder["maker_fee"] is None
    assert len(ladder["rows"]) == 10
    first = ladder["rows"][0]
    assert first["buy"] == "60000" and first["sell"] == "61000"
    assert first["net_fraction"] is None and first["net_quote"] is None
    assert first["gross_quote"] is not None
    assert first["state"] == "NO_ORDER"
    assert ladder["rows"][4]["state"] == "WAITING_TO_BUY"
    assert ladder["position"]["last_price"] == "64500"
    assert ladder["position"]["age_seconds"] == 300
    assert ladder["position"]["take_profit"] is None
    assert ladder["position"]["stop_loss"]["price"] == "57000.00"
    assert ladder["recorded"] == {
        "completed_cycles": 6,
        "grid_profit": "30",
        "average_profit": "5",
    }


def test_bot_list_has_a_grid_step_column_and_no_ladder_is_a_dash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _text(ListBotsVerb(), capsys)

    head = next(line for line in out.splitlines() if line.startswith("ID"))
    assert "GRID STEP" in head
    row = next(line for line in out.splitlines() if line.startswith("aaaaaa"))
    assert "1.45% (top) to 1.67% (bottom)" in row
    draft = next(line for line in out.splitlines() if line.startswith("cccccc"))
    assert "1.45%" not in draft
    assert "—" in draft
