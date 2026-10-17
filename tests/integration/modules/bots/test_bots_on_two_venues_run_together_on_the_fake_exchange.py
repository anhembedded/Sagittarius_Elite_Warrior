"""`EPIC-029J` J1a - one active bot per venue: a Spot Testnet bot and a Futures Testnet bot run
together in one composed app, over the one fake exchange.

@details Real everything but the network and the websocket (`two_venues_bots_world`). Both bots
trade `BTCUSDT`, so the client order id's tag is all that tells whose an order or a fill is. Each
test states one promise of the slice: both start; a second bot on a venue that is taken is
refused, naming the venue; a fill and its profit reach only the bot whose tag it carries; stopping
one leaves the other resting; an Emergency Stop on one venue halts that venue's bot and leaves the
other venue's bot and its orders alone.
"""

from __future__ import annotations

import json
import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    parse_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_steps import (
    StartPlannedBots,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .grid_fake_exchange import FakeExchange, ladder
from .two_venues_bots_world import (
    FUTURES,
    GRIDS,
    SPOT,
    SYMBOL,
    BootedTwoVenues,
    booted_two_venues,
)

S = BotLifecycleState


def _create(app: BootedTwoVenues, venue: TradingVenue, name: str = "grid") -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand(name, "grid", venue, SYMBOL, GRIDS[venue])
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    return created.bot_id


def _start(app: BootedTwoVenues, bot_id: str) -> BotCommandResult:
    started = app.engine.dispatch(
        StartBotCommand, StartBotCommand(bot_id, real_money_confirmed=True)
    )
    assert isinstance(started, BotCommandResult)
    return started


def _both_running(app: BootedTwoVenues) -> tuple[str, str]:
    spot = _create(app, SPOT)
    futures = _create(app, FUTURES)
    for bot_id in (spot, futures):
        started = _start(app, bot_id)
        assert started.accepted, started.message
    return spot, futures


def test_a_spot_bot_and_a_futures_bot_run_together_each_with_its_own_orders(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        spot, futures = _both_running(app)

        assert (app.bot(spot).state, app.bot(futures).state) == (S.RUNNING, S.RUNNING)
        spot_resting = app.resting(SPOT)
        futures_resting = app.resting(FUTURES)
        assert spot_resting == set(ladder(app.runtime(spot)))
        assert futures_resting == set(ladder(app.runtime(futures)))
        assert spot_resting and futures_resting
        assert {tag_of(oid) for oid in spot_resting} == {spot}
        assert {tag_of(oid) for oid in futures_resting} == {futures}


def test_a_second_bot_on_a_venue_that_is_taken_is_refused_naming_the_venue(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        spot, futures = _both_running(app)
        another_spot = _create(app, SPOT, "second spot")
        another_futures = _create(app, FUTURES, "second futures")

        refused_spot = _start(app, another_spot)
        refused_futures = _start(app, another_futures)

        assert refused_spot.refusal is BotRefusal.ONE_ACTIVE_BOT_PER_VENUE
        assert f"A bot on Spot Testnet is still active ({spot})" in refused_spot.message
        assert refused_futures.refusal is BotRefusal.ONE_ACTIVE_BOT_PER_VENUE
        assert (
            f"A bot on Futures Testnet is still active ({futures})"
            in refused_futures.message
        )
        assert app.bot(another_spot).state is S.DRAFT
        assert app.bot(another_futures).state is S.DRAFT
        assert app.resting(SPOT) == set(ladder(app.runtime(spot)))


def test_a_fill_and_its_profit_reach_only_the_bot_whose_tag_it_carries(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        spot, futures = _both_running(app)
        futures_before = app.runtime(futures)

        app.move_price(SPOT, 48700)  # the 48,800 buy fills, its sell goes one up
        app.move_price(SPOT, 49700)  # that sell fills: one cycle

        spot_runtime = app.runtime(spot)
        assert spot_runtime.completed_cycles == 1
        assert spot_runtime.realised_profit > 0
        assert app.runtime(futures) == futures_before

        spot_after = app.runtime(spot)
        app.move_price(FUTURES, 62900)  # the 63,000 buy fills on Futures

        futures_runtime = app.runtime(futures)
        assert futures_runtime.inventory > futures_before.inventory
        assert futures_runtime.completed_cycles == 0
        assert app.runtime(spot) == spot_after
        assert app.resting(SPOT) == set(ladder(app.runtime(spot)))
        assert app.resting(FUTURES) == set(ladder(app.runtime(futures)))


def test_stopping_one_bot_leaves_the_other_venues_bot_running(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        spot, futures = _both_running(app)

        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(spot, ExposureHandling.KEEP)
        )
        assert isinstance(stopped, BotCommandResult)
        assert stopped.accepted, stopped.message

        assert app.bot(spot).state is S.STOPPED
        assert app.resting(SPOT) == set()
        assert app.bot(futures).state is S.RUNNING
        assert app.resting(FUTURES) == set(ladder(app.runtime(futures)))
        # the venue spot's bot held is free again; the other is still taken
        again = _start(app, spot)
        assert again.accepted, again.message


def test_an_emergency_stop_on_one_venue_halts_its_bot_and_none_on_the_other(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        spot, futures = _both_running(app)
        spot_ladder = app.resting(SPOT)

        app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=FUTURES))
        app.deliver()

        assert app.bot(futures).state is S.HALTED
        assert app.runtime(futures).reason is GridReason.SWITCH_OFF
        assert app.resting(FUTURES) == set()
        assert app.scopes[FUTURES].session_state.enabled is False
        assert app.bot(spot).state is S.RUNNING
        assert app.scopes[SPOT].session_state.enabled is True
        assert app.resting(SPOT) == spot_ladder == set(ladder(app.runtime(spot)))


class _Records(logging.Handler):
    """`caplog` sees nothing: the composed app turns propagation off, so listen on the logger."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _planned(name: str, venue: TradingVenue) -> dict[str, object]:
    return {
        "name": name,
        "kind": "grid",
        "venue": venue.value,
        "symbol": SYMBOL,
        "params": GRIDS[venue],
        "desired_state": "running",
    }


def test_start_planned_starts_one_bot_per_venue_and_names_the_one_it_refuses(
    both_venues: FakeExchange,
) -> None:
    """The headless host's `run --start-planned` asks the same Start the screen does: of two
    planned bots on one venue only one starts, and the other venue's bot starts beside it."""
    handler, logger = _Records(), logging.getLogger("App.Operations.Host")
    logger.addHandler(handler)
    try:
        with booted_two_venues(both_venues) as app:
            container = app.engine.container
            plan = json.dumps(
                {
                    "schema": "sew.bot-plan/1",
                    "bots": [
                        _planned("spot a", SPOT),
                        _planned("spot b", SPOT),
                        _planned("futures a", FUTURES),
                    ],
                }
            )
            PlanApplier(
                container.resolve(ICommandDispatcher),
                container.resolve(IAppliedPlanStore),
            ).apply(
                parse_plan(plan, container.resolve(IBotKindCatalog)), PrunePolicy.KEEP
            )

            StartPlannedBots(
                container.resolve(IBotPlan), container.resolve(ICommandDispatcher), None
            ).run()

            listing = container.resolve(ICommandDispatcher).dispatch(
                ListBotsQuery, ListBotsQuery()
            )
            states = {bot.name: app.bot(bot.bot_id).state for bot in listing.bots}  # type: ignore[attr-defined]
            assert states["futures a"] is S.RUNNING
            assert sorted(states[n] for n in ("spot a", "spot b")) == [
                S.DRAFT,
                S.RUNNING,
            ]
    finally:
        logger.removeHandler(handler)
    refused = [
        r.getMessage()
        for r in handler.records
        if r.levelno == logging.WARNING and "was not started" in r.getMessage()
    ]
    assert len(refused) == 1
    assert "ONE_ACTIVE_BOT_PER_VENUE" in refused[0]
    assert "A bot on Spot Testnet is still active" in refused[0]
