"""`EPIC-039H` - sibling parity (`EPIC-037D`'s idea): the Spot Grid and the Futures Long Grid walk
the same scenario table and agree where they must.

@details Both executors are the real ones in the composed app over the fake exchange; what a world
supplies is only how a price move, a start and a stop are made on its venue. A scenario is a path
of prices written as fractions of the range, and after every step the two ladders must be in the
same state at every level, have booked the same number of cycles, and a stopped bot must say the
same reason with nothing resting. They differ, by design, in what a level is worth (Spot sizes by
capital, Futures by quantity; Futures pays no base fee), so profit is compared by sign, not amount.

Not in the table, covered by each executor's own journeys: a partial fill (the Spot fake has no
partial fill), a rejected counter, a stream gap (`test_a_user_stream_gap_on_the_fake_exchange.py`,
`test_a_futures_grid_halts_and_recovers_on_the_fake_exchange.py`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
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
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)

from .futures_bots_world import GRID as FUTURES_GRID
from .futures_bots_world import booted_futures_bots
from .futures_fake_exchange import FUTURES
from .futures_fake_exchange import SYMBOL as FUTURES_SYMBOL
from .grid_fake_exchange import GRID as SPOT_GRID
from .grid_fake_exchange import SPOT, FakeExchange, booted

S = BotLifecycleState
D = Decimal
_AT = datetime(2026, 10, 13, 9, tzinfo=UTC)

#: Four grids, five rungs, the middle one nearest the price at the start: two buys, two sells.
_SPOT_CONFIG = {
    **SPOT_GRID,
    "grid_count": "4",
    "capital_quote": "1600",
    "stop_loss": "price:46000",
}
_FUTURES_CONFIG = {**FUTURES_GRID, "stop_loss": "price:60000"}
_SPOT_RANGE = (D(48000), D(52000))
_FUTURES_RANGE = (D(62000), D(66000))


@dataclass
class World:
    """One venue's side of a scenario: how to make a start, a price move and a stop."""

    lower: Decimal
    upper: Decimal
    start: Callable[[], str]
    move: Callable[[Decimal], None]
    stop_loss_crossed: Callable[[Decimal], None]
    state: Callable[[str], BotLifecycleState]
    runtime: Callable[[str], GridRuntime]
    resting: Callable[[], int]
    stop: Callable[[str], None]

    def at(self, fraction: str) -> Decimal:
        return self.lower + (self.upper - self.lower) * D(fraction)


def _ladder(runtime: GridRuntime) -> list[tuple[int, str, str | None]]:
    return [
        (
            level.index,
            level.state.name,
            None if level.order is None else level.order.side.name,
        )
        for level in runtime.levels
    ]


def _created(app_dispatch, venue, symbol, config) -> str:
    created = app_dispatch(
        CreateBotCommand, CreateBotCommand("parity", "grid", venue, symbol, config)
    )
    assert isinstance(created, BotCommandResult) and created.bot_id, created
    started = app_dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(started, BotCommandResult)
    assert started.accepted, started.message
    return created.bot_id


def _stopped(app_dispatch, bot_id: str) -> None:
    """Leaves the shared data root with no active bot (ADR D20) for the next world."""
    stopped = app_dispatch(
        StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
    )
    assert isinstance(stopped, BotCommandResult)
    assert stopped.accepted, stopped.message


@contextmanager
def _spot_world(exchange: FakeExchange) -> Iterator[World]:
    with booted(exchange) as app:

        def tick(price: Decimal) -> None:
            app.engine.event_bus.emit(
                MarketTickEvent(
                    MarketData(
                        symbol="BTCUSDT",
                        interval="1m",
                        open_time=_AT,
                        open_price=float(price),
                        high_price=float(price),
                        low_price=float(price),
                        close_price=float(price),
                        volume=1.0,
                        close_time=_AT,
                        quote_asset_volume=1.0,
                        number_of_trades=1,
                        taker_buy_base_asset_volume=1.0,
                        taker_buy_quote_asset_volume=1.0,
                    ),
                    market_type=MarketType.SPOT,
                    market_data_venue=SPOT.market_data_venue,
                )
            )

        def stop_loss_crossed(price: Decimal) -> None:
            app.move_price(int(price))
            tick(price)

        bots: list[str] = []

        def start() -> str:
            bots.append(_created(app.engine.dispatch, SPOT, "BTCUSDT", _SPOT_CONFIG))
            return bots[0]

        yield World(
            *_SPOT_RANGE,
            start,
            lambda price: app.move_price(int(price)),
            stop_loss_crossed,
            lambda bot_id: app.bot(bot_id).state,
            app.runtime,
            lambda: len(_open_spot_orders(app)),
            lambda bot_id: _stopped(app.engine.dispatch, bot_id),
        )


def _open_spot_orders(app) -> list[object]:
    return list(app.urls.spot_account.open_orders("BTCUSDT"))


@contextmanager
def _futures_world(futures: FakeExchange) -> Iterator[World]:
    with booted_futures_bots(futures) as app:
        bots: list[str] = []

        def start() -> str:
            bots.append(
                _created(app.engine.dispatch, FUTURES, FUTURES_SYMBOL, _FUTURES_CONFIG)
            )
            return bots[0]

        def stop_loss_crossed(price: Decimal) -> None:
            # One move through two resting buys would deliver two reports at once, which the
            # world's delivery cannot take; the mark crossing is what is under test.
            futures.urls.futures_book.faults.hold_fills = True
            app.move_price(price)  # the fake's one price is the mark too
            app.ticker.fire()
            app.deliver()

        yield World(
            *_FUTURES_RANGE,
            start,
            app.move_price,
            stop_loss_crossed,
            lambda bot_id: app.bot(bot_id).state,
            app.runtime,
            lambda: len(app.resting()),
            lambda bot_id: _stopped(app.engine.dispatch, bot_id),
        )


@pytest.fixture
def spot_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `futures` fixture patches both families' testnet URLs of one fake server and sets only
    the Futures key; the Spot world needs its own."""
    monkeypatch.setenv(SPOT_ENV_API_KEY, "fake-key")
    monkeypatch.setenv(SPOT_ENV_API_SECRET, "fake-secret")


#: A scenario is a path of prices as fractions of the range (0 is `lower`, 1 is `upper`); the middle
#: rung is the one nearest the start. Each step crosses one rung.
_WALK = ["0.225", "0.525", "0.775", "1.025", "0.725"]
_ROUND_TRIP = ["0.225", "0.525", "0.225", "0.525"]


@dataclass(frozen=True)
class Snapshot:
    """What must agree between the siblings after a step."""

    ladder: list[tuple[int, str, str | None]]
    cycles: int
    profitable: bool
    state: BotLifecycleState


def _walked(world: World, path: list[str]) -> list[Snapshot]:
    bot_id = world.start()

    def snapshot() -> Snapshot:
        runtime = world.runtime(bot_id)
        return Snapshot(
            _ladder(runtime),
            runtime.completed_cycles,
            runtime.realised_profit > 0,
            world.state(bot_id),
        )

    taken = [snapshot()]
    for fraction in path:
        world.move(world.at(fraction))
        taken.append(snapshot())
    world.stop(bot_id)
    return taken


@pytest.mark.parametrize("path", [_WALK, _ROUND_TRIP], ids=["walk", "round-trip"])
def test_both_ladders_are_in_the_same_state_after_every_step_of_a_path(
    futures: FakeExchange, spot_key: None, path: list[str]
) -> None:
    with _spot_world(futures) as spot:
        spot_steps = _walked(spot, path)
    with _futures_world(futures) as long_:
        futures_steps = _walked(long_, path)

    assert futures_steps == spot_steps
    assert all(step.state is S.RUNNING for step in spot_steps)
    assert spot_steps[-1].cycles > 0, (
        "the path completes a cycle, so the comparison bites"
    )


def _stopped_by_stop_loss(
    world: World,
) -> tuple[BotLifecycleState, GridReason | None, int]:
    bot_id = world.start()
    world.stop_loss_crossed(world.at("-0.6"))
    return world.state(bot_id), world.runtime(bot_id).reason, world.resting()


def test_both_stop_on_a_stop_loss_for_the_same_reason_with_nothing_resting(
    futures: FakeExchange, spot_key: None
) -> None:
    with _spot_world(futures) as spot:
        spot_outcome = _stopped_by_stop_loss(spot)
    with _futures_world(futures) as long_:
        futures_outcome = _stopped_by_stop_loss(long_)

    assert spot_outcome == futures_outcome == (S.STOPPED, GridReason.STOP_LOSS, 0)
