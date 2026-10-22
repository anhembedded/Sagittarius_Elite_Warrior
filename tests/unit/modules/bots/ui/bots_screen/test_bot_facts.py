"""`EPIC-029F` — the detail panel's figures."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import (
    PnlSummary,
    pnl_summary,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    NO_VALUE,
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_panel import (
    BotPlanPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    BotsTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_rows import (
    PROPERTY_KEYS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    started_ladder,
)

from .bots_screen_fixtures import NOW, stored

_EARNINGS = {"realised", "grid_profit", "cycles", "total_pnl", "unrealised"}
_HELD = BotProgress(
    realised_profit=Decimal("12.5"),
    completed_cycles=3,
    open_orders=2,
    inventory=Decimal("0.01"),
    average_cost=Decimal(64000),
    reason="switch_off",
    reason_detail="trading turned off",
)


def _running(progress: BotProgress | None = _HELD) -> BotSnapshot:
    return BotSnapshot.of(stored("a00001", BotLifecycleState.HALTED).bot, progress)


def _pnl(
    mark: str | None, inventory: str = "0.01", realised_total: str = "20"
) -> PnlSummary:
    runtime = GridRuntime(
        started_ladder().levels,
        inventory=Decimal(inventory),
        cost=Decimal(inventory) * 64000,
        realised_profit=Decimal("12.5"),
        realised_total=Decimal(realised_total),
        start_price=Decimal(60000),
        mark_price=Decimal(mark) if mark else None,
    )
    return pnl_summary(runtime, capital=Decimal(1000))


_PRICED = replace(_HELD, mark_price=Decimal(65000), pnl=_pnl("65000"))


def test_unrealised_pnl_is_what_the_held_base_gained_at_the_bots_own_price() -> None:
    facts = bot_facts(_running(_PRICED), NOW)

    assert facts.unrealised == "▲ +10.00 at 65,000.00"
    lower = replace(_PRICED, mark_price=Decimal(63000), pnl=_pnl("63000"))
    assert bot_facts(_running(lower), NOW).unrealised == "▼ -10.00 at 63,000.00"


def test_grid_profit_comes_first_with_the_total_and_the_unrealised_kept_apart() -> None:
    facts = bot_facts(_running(_PRICED), NOW)

    assert facts.total_pnl == "▲ +30.00"
    assert facts.grid_profit == "▲ +12.50"
    # `BOT-229`: the order that adds up: realised, of which the grid cycles, what is held, the total.
    assert [key for key in PROPERTY_KEYS if key in _EARNINGS] == [
        "realised",
        "grid_profit",
        "cycles",
        "unrealised",
        "total_pnl",
    ]


def test_the_hodl_benchmark_is_shown_beside_the_total() -> None:
    """1000 at 60 000 buys 1/60 BTC; at 65 000 that is 1083.33: +83.33."""
    assert bot_facts(_running(_PRICED), NOW).hodl == "▲ +83.33"


def test_without_a_price_the_bot_heard_the_unrealised_and_the_total_say_so() -> None:
    facts = bot_facts(_running(replace(_HELD, pnl=_pnl(None))), NOW)

    assert facts.unrealised == "no price yet"
    assert facts.total_pnl == "no price yet"
    assert facts.hodl == "—"


def test_a_flat_bot_shows_no_unrealised_and_a_total_equal_to_what_it_realised() -> None:
    flat = replace(
        _PRICED,
        inventory=Decimal(0),
        average_cost=None,
        pnl=_pnl("65000", inventory="0"),
    )

    facts = bot_facts(_running(flat), NOW)

    assert facts.unrealised == "—"
    assert facts.total_pnl == "▲ +20.00"


def test_fees_that_could_not_be_priced_make_the_total_say_it_is_short() -> None:
    short = replace(_PRICED, pnl=replace(_PRICED.pnl, unpriced_fees=2))

    assert "2 fees could not be priced" in bot_facts(_running(short), NOW).total_pnl


def test_the_state_carries_its_reason_and_capital_comes_from_the_kinds_key() -> None:
    facts = bot_facts(_running(), NOW)

    assert facts.state == "Halted — trading turned off"
    assert facts.capital == "1000"
    assert facts.grid_profit == "▲ +12.50"


def test_running_time_counts_from_the_run_start_and_stops_at_rest() -> None:
    """A duration the formatter writes (`EPIC-033N`), not text written here."""
    elapsed = timedelta(days=1, hours=2, minutes=5)
    bot = replace(_running(), run_started_at=NOW - elapsed)

    assert bot_facts(bot, NOW).running_time == elapsed
    stopped = replace(bot, state=BotLifecycleState.STOPPED)
    assert bot_facts(stopped, NOW).running_time is None


def test_a_run_started_in_the_future_has_run_for_nothing() -> None:
    """A clock behind the stored start never reads as a negative time."""
    bot = replace(_running(), run_started_at=NOW + timedelta(minutes=3))

    assert bot_facts(bot, NOW).running_time == timedelta(0)


def test_base_earlier_runs_left_is_named_with_its_cost_and_otherwise_shows_nothing() -> (
    None
):
    """`BUG-196` — the figure a new run does not trade is not left unsaid."""
    none = bot_facts(_running(), NOW).earlier_runs
    left = bot_facts(
        _running(
            replace(
                _HELD,
                earlier_runs_base=Decimal("0.0083"),
                earlier_runs_cost=Decimal("20.5"),
            )
        ),
        NOW,
    ).earlier_runs

    assert none == NO_VALUE
    assert "0.0083" in left
    assert "not traded by this run" in left


def _on(venue: TradingVenue, pnl: PnlSummary | None) -> BotSnapshot:
    held = replace(_HELD, pnl=pnl)
    return replace(_running(held), venue=venue)


_COSTS = PnlSummary(
    total=Decimal("9.5"),
    realised=Decimal(12),
    unrealised=Decimal("0.5"),
    grid_profit=Decimal(12),
    hodl=None,
    unpriced_fees=0,
    commissions=Decimal("0.0042"),
    funding=Decimal("-0.0317"),
)


def test_a_futures_bot_shows_commissions_and_funding_apart_from_the_grid_profit() -> (
    None
):
    """`EPIC-039J`: trading's costs are their own figures, funding is part of the total and
    never of the grid profit, and a payment far below a cent is not printed as zero."""
    facts = bot_facts(_on(TradingVenue.FUTURES_TESTNET, _COSTS), NOW)

    assert facts.shows_costs
    assert facts.commissions == "0.0042"
    assert facts.funding == "-0.0317"
    assert facts.grid_profit != facts.funding


def test_a_spot_bot_shows_no_cost_rows_and_its_figures_are_unchanged() -> None:
    facts = bot_facts(_on(TradingVenue.SPOT_TESTNET, _COSTS), NOW)

    assert not facts.shows_costs
    assert (
        facts.total_pnl
        == bot_facts(_running(replace(_HELD, pnl=_COSTS)), NOW).total_pnl
    )


def test_a_futures_bot_without_a_run_account_says_no_value_for_its_costs() -> None:
    facts = bot_facts(_on(TradingVenue.FUTURES_TESTNET, None), NOW)

    assert (facts.commissions, facts.funding) == (NO_VALUE, NO_VALUE)


def _panel_showing(qtbot, venue: TradingVenue):  # type: ignore[no-untyped-def]
    model = BotsViewModel()
    panel = BotPlanPanel(model)
    qtbot.addWidget(panel)
    bot = _on(venue, _COSTS)
    model.set_selected(bot)
    model.set_facts(bot_facts(bot, NOW))
    return panel


def _row_shown(panel: BotPlanPanel, key: str) -> bool:
    return panel.properties.row_is_shown(key)


def test_the_cost_rows_are_on_screen_for_futures_and_not_for_spot(qtbot) -> None:
    futures = _panel_showing(qtbot, TradingVenue.FUTURES_TESTNET)
    spot = _panel_showing(qtbot, TradingVenue.SPOT_TESTNET)

    assert _row_shown(futures, "commissions") and _row_shown(futures, "funding")
    assert futures.properties.shown_value("funding") == "-0.0317"
    assert not _row_shown(spot, "commissions") and not _row_shown(spot, "funding")
    assert _row_shown(spot, "grid_profit") and _row_shown(futures, "grid_profit")


def test_the_bots_table_shows_realised_between_cycles_and_the_total(qtbot) -> None:
    """`BOT-231`: the money sold so far (net of fees) is a column, beside Grid profit it contains."""
    model = BotsTableModel()
    model.set_rows([_running(_PRICED)])
    keys = [spec.key for spec in BotsTableModel.COLUMNS]

    assert keys[-4:] == [
        "grid_profit.signed",
        "cycles",
        "realised.signed",
        "profit.signed",
    ]
    assert BotsTableModel.COLUMNS[-2].title == "Realised"
    cells = [model.index(0, keys.index(key)).data() for key in keys[-4:]]
    assert cells == [Decimal("12.5"), 3, _PRICED.pnl.realised, Decimal(30)]
    assert _PRICED.pnl.realised != Decimal("12.5"), "must differ from grid profit"


def test_the_realised_cell_is_blank_while_the_pnl_is_not_judged(qtbot) -> None:
    model = BotsTableModel()
    unjudged = replace(_PRICED, pnl=None)
    model.set_rows([_running(unjudged)])

    assert model.index(0, model.column("realised.signed")).data() is None


def test_each_earnings_figure_says_whether_it_is_a_profit_or_a_loss() -> None:
    """`EPIC-043C`: the Plan dock paints a figure by what it means; zero and unknown say nothing."""
    facts = bot_facts(_running(_PRICED), NOW)

    assert facts.tones["grid_profit"] is Tone.POSITIVE
    assert facts.tones["total_pnl"] is Tone.POSITIVE
    assert facts.tones["unrealised"] is Tone.POSITIVE
    assert facts.tones["hodl"] is Tone.POSITIVE
    assert bot_facts(_running(None), NOW).tones["total_pnl"] is Tone.NEUTRAL


def test_the_realised_figure_is_shown_beside_the_grid_profit_with_its_basis() -> None:
    """`BOT-229`: realised (against the average cost) is its own row, the basis is said once, and a
    bot with no run account shows neither."""
    facts = bot_facts(_running(_PRICED), NOW)

    assert facts.realised != NO_VALUE
    assert facts.earnings_basis.startswith(
        "Realised is measured against the average cost"
    )
    assert bot_facts(_running(None), NOW).earnings_basis == NO_VALUE
