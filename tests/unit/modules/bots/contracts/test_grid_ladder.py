"""`BOT-193` - the ladder, its summary and the price position, from the saved record only.

@details The business promises, each asserted on the figure and not on a private call: the rows
equal `derive`'s grids (the one arithmetic of the report); an arithmetic and a geometric bot differ
as `grid_spacing.py` says; the ladder follows the *current* saved parameters; a figure without a
price, a fee or a run is `None`, never zero; the states are the saved run's and only when the run is
this ladder.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotOrderLine,
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    NO_LADDER_FOR_KIND,
    RUN_DIFFERS_NOTE,
    GridLadder,
    LadderState,
    LadderUnavailable,
    grid_ladder_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_derived import derive
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import plan
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    LAST_PRICE,
    TERMS,
)

_NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)
_FEE = TERMS.maker_fee
_STEP_UNITS = Decimal("1e-12")


def _bot(
    config: dict[str, str] | None = None,
    progress: BotProgress | None = None,
    venue: TradingVenue = TradingVenue.SPOT_TESTNET,
    kind: str = "grid",
) -> BotSnapshot:
    return BotSnapshot(
        bot_id="a00001",
        name="grid",
        kind=kind,
        venue=venue,
        symbol="BTCUSDT",
        state=BotLifecycleState.RUNNING,
        created_at=_NOW - timedelta(days=1),
        run_started_at=_NOW - timedelta(hours=3),
        config={**CONFIG, **(config or {})},
        progress=progress,
    )


def _order(level: int, side: str, price: str) -> BotOrderLine:
    return BotOrderLine(
        level, side, Decimal(price), Decimal(1), Decimal(0), f"c{level}"
    )


def _progress(**fields: object) -> BotProgress:
    base = BotProgress(
        realised_profit=Decimal(30),
        completed_cycles=6,
        open_orders=0,
        inventory=Decimal(0),
        average_cost=None,
        reason="",
        reason_detail="",
    )
    return replace(base, **fields)


def _ladder(bot: BotSnapshot, maker_fee: Decimal | None = None) -> GridLadder:
    ladder = grid_ladder_of(bot, _NOW, maker_fee)
    assert isinstance(ladder, GridLadder)
    return ladder


def test_the_rows_equal_derives_grids_to_the_cent() -> None:
    params = GridParams.from_config(CONFIG)
    derived = derive(params, TERMS, plan(params, TERMS, LAST_PRICE))

    ladder = _ladder(_bot(), _FEE)

    assert [(r.buy, r.sell) for r in ladder.rows] == [
        (g.buy, g.sell) for g in derived.grids
    ]
    assert [r.step_fraction for r in ladder.rows] == [
        g.step_fraction for g in derived.grids
    ]
    assert [r.net_fraction for r in ladder.rows] == [
        g.net_fraction for g in derived.grids
    ]
    assert ladder.summary.smallest_step_fraction == derived.smallest_step_fraction
    assert ladder.summary.largest_step_fraction == derived.largest_step_fraction
    assert ladder.summary.average_cycle_quote == derived.cycle_profit_quote


def test_an_arithmetic_step_shrinks_towards_the_top_and_a_geometric_one_does_not() -> (
    None
):
    arithmetic = _ladder(_bot())
    geometric = _ladder(_bot({"spacing": "GEOMETRIC"}))

    steps = [row.step_fraction for row in arithmetic.rows]
    assert steps == sorted(steps, reverse=True)
    assert steps[0] > steps[-1]
    geometric_steps = [row.step_fraction for row in geometric.rows]
    assert max(geometric_steps) - min(geometric_steps) < _STEP_UNITS


def test_the_ladder_follows_the_current_saved_parameters() -> None:
    before = _ladder(_bot())
    edited = _ladder(_bot({"lower": "50000", "upper": "80000", "grid_count": "6"}))

    assert len(before.rows) == 10
    assert len(edited.rows) == 6
    assert edited.rows[0].buy == Decimal(50000)
    assert edited.rows[-1].sell == Decimal(80000)


def test_without_a_fee_the_net_is_unknown_and_the_profit_is_before_fees() -> None:
    ladder = _ladder(_bot())

    assert all(
        row.net_fraction is None and row.net_quote is None for row in ladder.rows
    )
    assert all(
        row.gross_quote is not None and row.gross_quote > 0 for row in ladder.rows
    )
    assert ladder.summary.maker_fee is None
    assert ladder.summary.average_cycle_quote is not None


def test_a_fee_larger_than_the_step_makes_the_net_negative_not_hidden() -> None:
    ladder = _ladder(_bot(), Decimal("0.05"))

    assert all(
        row.net_fraction is not None and row.net_fraction < 0 for row in ladder.rows
    )
    assert all(row.net_quote is not None and row.net_quote < 0 for row in ladder.rows)


def test_no_price_heard_is_no_price_and_never_a_zero_distance() -> None:
    position = _ladder(_bot(progress=_progress())).position

    assert position.last_price is None
    assert position.age_seconds is None
    assert position.lower.distance_fraction is None
    assert position.upper.distance_fraction is None
    assert position.stop_loss is not None
    assert position.stop_loss.distance_fraction is None


def test_the_distances_are_the_arithmetic_on_the_saved_last_price() -> None:
    heard = _NOW - timedelta(minutes=5)
    progress = _progress(mark_price=Decimal(64000), mark_price_at=heard)

    position = _ladder(_bot(progress=progress)).position

    assert position.last_price == Decimal(64000)
    assert position.age_seconds == 300
    assert position.lower.distance_fraction == Decimal(-4000) / Decimal(64000)
    assert position.upper.distance_fraction == Decimal(6000) / Decimal(64000)
    assert position.stop_loss is not None
    assert position.stop_loss.price == Decimal(57000)
    assert position.stop_loss.distance_fraction == Decimal(-7000) / Decimal(64000)
    assert position.take_profit is not None
    assert position.take_profit.price == Decimal(73500)
    assert position.take_profit.distance_fraction == Decimal(9500) / Decimal(64000)


def test_an_exit_that_is_off_is_not_a_mark() -> None:
    position = _ladder(_bot({"stop_loss": "off", "take_profit": "off"})).position

    assert position.stop_loss is None
    assert position.take_profit is None


def test_a_price_heard_in_the_future_is_age_zero_not_negative() -> None:
    progress = _progress(
        mark_price=Decimal(64000), mark_price_at=_NOW + timedelta(seconds=30)
    )

    assert _ladder(_bot(progress=progress)).position.age_seconds == 0


def test_a_price_without_its_moment_has_an_unknown_age() -> None:
    progress = _progress(mark_price=Decimal(64000))

    position = _ladder(_bot(progress=progress)).position

    assert position.last_price == Decimal(64000)
    assert position.age_seconds is None


@pytest.mark.parametrize(
    ("venue", "has_liquidation"),
    [(TradingVenue.SPOT_TESTNET, False), (TradingVenue.FUTURES_TESTNET, True)],
)
def test_only_a_position_venue_has_a_liquidation_price_to_say_is_unknown(
    venue: TradingVenue, has_liquidation: bool
) -> None:
    config = {"direction": "LONG", "leverage": "2"} if has_liquidation else {}

    position = _ladder(_bot(config, venue=venue)).position

    assert position.has_liquidation_price is has_liquidation


def test_a_futures_cycle_is_sized_by_the_one_quantity_at_the_highest_level() -> None:
    config = {"direction": "LONG", "leverage": "2"}

    futures = _ladder(_bot(config, venue=TradingVenue.FUTURES_TESTNET))
    spot = _ladder(_bot())

    quantity = Decimal(10000) * 2 / 10 / Decimal(70000)
    assert futures.rows[0].gross_quote == quantity * Decimal(60000) * (
        futures.rows[0].step_fraction
    )
    assert spot.rows[0].gross_quote == Decimal(1000) * spot.rows[0].step_fraction


def test_the_states_are_the_saved_runs_where_it_is_this_ladder() -> None:
    orders = (
        _order(0, "BUY", "60000"),
        _order(1, "BUY", "61000"),
        _order(2, "BUY", "62000"),
        _order(3, "BUY", "63000"),
        _order(4, "BUY", "64000"),
        _order(6, "SELL", "66000"),
        _order(7, "SELL", "67000"),
        _order(8, "SELL", "68000"),
        _order(9, "SELL", "69000"),
        _order(10, "SELL", "70000"),
    )
    ladder = _ladder(_bot(progress=_progress(orders=orders)))

    states = [row.state for row in ladder.rows]

    assert states[:4] == [LadderState.WAITING_TO_BUY] * 4
    assert states[4] is LadderState.WAITING_TO_BUY
    assert states[5] is LadderState.WAITING_TO_SELL
    assert states[6:] == [LadderState.WAITING_TO_SELL] * 4
    assert ladder.run_note == ""


def test_the_grid_the_price_stands_in_waits_to_buy_and_to_sell() -> None:
    orders = (_order(4, "BUY", "64000"), _order(5, "SELL", "65000"))

    ladder = _ladder(_bot(progress=_progress(orders=orders)))

    assert ladder.rows[4].state is LadderState.WAITING_BOTH


def test_a_run_with_nothing_resting_has_no_order_on_any_grid() -> None:
    ladder = _ladder(_bot(progress=_progress()))

    assert {row.state for row in ladder.rows} == {LadderState.NO_ORDER}


def test_a_tick_rounded_resting_price_is_still_this_ladder() -> None:
    orders = (_order(4, "BUY", "63999.99"),)

    ladder = _ladder(_bot(progress=_progress(orders=orders)))

    assert ladder.rows[4].state is LadderState.WAITING_TO_BUY
    assert ladder.run_note == ""


def test_a_run_of_another_ladder_claims_no_state_and_says_so() -> None:
    edited = {"lower": "50000", "upper": "80000", "grid_count": "6"}
    orders = (_order(4, "BUY", "64000"),)

    ladder = _ladder(_bot(edited, _progress(orders=orders)))

    assert {row.state for row in ladder.rows} == {LadderState.NOT_RECORDED}
    assert ladder.run_note == RUN_DIFFERS_NOTE


def test_a_level_beyond_the_ladder_is_another_ladder() -> None:
    orders = (_order(11, "BUY", "64000"),)

    ladder = _ladder(_bot(progress=_progress(orders=orders)))

    assert ladder.run_note == RUN_DIFFERS_NOTE


def test_a_bot_with_no_run_claims_no_state_and_no_note() -> None:
    ladder = _ladder(_bot())

    assert {row.state for row in ladder.rows} == {LadderState.NOT_RECORDED}
    assert ladder.run_note == ""
    assert ladder.recorded.grid_profit is None
    assert ladder.recorded.average_profit is None


def test_the_recorded_average_is_the_profit_the_cycles_booked_over_them() -> None:
    recorded = _ladder(_bot(progress=_progress())).recorded

    assert recorded.completed_cycles == 6
    assert recorded.grid_profit == Decimal(30)
    assert recorded.average_profit == Decimal(5)


def test_no_completed_cycle_has_no_average_not_a_zero_one() -> None:
    recorded = _ladder(
        _bot(progress=_progress(completed_cycles=0, realised_profit=Decimal(0)))
    ).recorded

    assert recorded.average_profit is None


def test_a_kind_without_a_ladder_says_so() -> None:
    assert grid_ladder_of(_bot(kind="dca"), _NOW) == LadderUnavailable(
        NO_LADDER_FOR_KIND
    )


def test_a_draft_without_parameters_names_what_is_missing() -> None:
    bot = replace(_bot(), config={})

    unavailable = grid_ladder_of(bot, _NOW)

    assert isinstance(unavailable, LadderUnavailable)
    assert "lower is missing" in unavailable.reason


def test_a_venue_with_no_market_profile_has_no_sized_figure_not_a_guess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder.venue_profile_of",
        lambda _venue: None,
    )

    ladder = _ladder(_bot(), _FEE)

    assert all(row.gross_quote is None and row.net_quote is None for row in ladder.rows)
    assert ladder.summary.average_cycle_quote is None
    assert not ladder.position.has_liquidation_price
