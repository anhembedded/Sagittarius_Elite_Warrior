"""`BUG-261` - the Plan group of the Live tab shows the figures of the design on screen.

@details A new Grid is designed in the Plan's editor before it is saved: the checks and the chart
already judge the edited parameters, but the property group read the saved config, so Capital, the
grid step, the profit per cycle, the edges and the exits read "—". The figures now come from the
same parameters the checks judge, and say they are not saved.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    GridLadder,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    DetailInputs,
    detail_for,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

NOW = datetime(2026, 10, 21, 9, tzinfo=UTC)

_DESIGN = {
    "lower": "100",
    "upper": "140",
    "grid_count": "4",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "price:90",
    "take_profit": "price:150",
}


def _unsaved_grid() -> BotSnapshot:
    """A bot that was created and not yet designed: its saved config holds no figure."""
    return BotSnapshot(
        bot_id="a3f9c1",
        name="grid",
        kind="grid",
        venue=TradingVenue.SPOT_TESTNET,
        symbol="BTCUSDT",
        state=BotLifecycleState.DRAFT,
        created_at=datetime(2026, 10, 21, tzinfo=UTC),
        run_started_at=None,
        config={},
    )


def test_the_design_on_screen_fills_the_plan_figures_and_says_it_is_not_saved() -> None:
    detail = detail_for(DetailInputs(_unsaved_grid(), None, None, NOW, edited=_DESIGN))

    assert detail.facts.capital == "1000"
    assert detail.facts.unsaved is True
    assert isinstance(detail.ladder, GridLadder)
    assert detail.ladder.rows[0].buy == Decimal(100)
    assert detail.ladder.rows[-1].sell == Decimal(140)


def test_without_an_edit_the_figures_are_the_saved_ones_and_not_marked() -> None:
    saved = replace(_unsaved_grid(), config=_DESIGN)

    detail = detail_for(DetailInputs(saved, None, None, NOW))

    assert detail.facts.capital == "1000"
    assert detail.facts.unsaved is False
