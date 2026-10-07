"""`EPIC-029E` — a live Grid in the composed app, against the fake Binance server.

@details `create_app()` builds everything: the bots module with its use cases,
runner, executors and event router, and trading with the Spot adapters over
`python-binance`, the owner budget, `ExecuteOrderCommandHandler`, Emergency
Stop and the venue's emission path (`SpotUserDataStream` →
`VenueEventEmitter` → the bus → `BotEventRouter`). What is substituted, and
why:
- the network: `python-binance` points at `run_binance_fake_server()`, the
  venue's key pair comes from the environment, and every `get_loop` binding
  returns one loop this file owns (`BUG-075`, as the F9 test does);
- the fake has no websocket, so its executionReports are handed to the
  venue's own stream (`_deliver`), as the owner-budget test does;
- the bot's queue and pacer. The queue runs each task on the poster's thread,
  one at a time and in posting order (a task posted while one runs waits for
  it), so a journey is deterministic without a wait. The pacer delivers the
  reports before each turn: the stream's delivery within the spacing that
  `grid_start_sequence`'s known limit names. The thread queue and the
  monotonic pacer have their own unit tests;
- the session is seeded as open: opening it would start the venue's
  websocket, which the fake does not speak (`EPIC-028S` §3). A restart
  opens it by publishing the event the opening publishes; the journey that
  starts from a closed session (`EPIC-034C`) stubs the stream's `start`, the
  one websocket call, and runs everything else for real.

At each step the exchange's open orders are asserted against the bot's own
ladder, price for price and id for id.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)

from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    BootedApp,
    FakeExchange,
    booted,
    ladder,
    resting,
    sides_by_price,
)

S = BotLifecycleState


def _started(app: BootedApp) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(started, BotCommandResult)
    assert started.accepted, started.message
    return created.bot_id


def test_a_grid_starts_cycles_replaces_a_cancel_and_halts_on_emergency_stop(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)

        assert app.bot(bot_id).state is S.RUNNING
        assert resting(app.urls) == ladder(app.runtime(bot_id))
        assert sides_by_price(app.runtime(bot_id)) == {
            Decimal(48000): "BUY",
            Decimal(48800): "BUY",
            Decimal(50400): "SELL",
            Decimal(51200): "SELL",
            Decimal(52000): "SELL",
        }

        app.move_price(48700)  # the 48,800 buy fills; its sell goes one up

        assert resting(app.urls) == ladder(app.runtime(bot_id))
        assert sides_by_price(app.runtime(bot_id))[Decimal(49600)] == "SELL"
        assert Decimal(48800) not in sides_by_price(app.runtime(bot_id))

        app.move_price(49700)  # that sell fills: one cycle, the buy back

        runtime = app.runtime(bot_id)
        assert resting(app.urls) == ladder(runtime)
        assert sides_by_price(runtime)[Decimal(48800)] == "BUY"
        assert runtime.completed_cycles == 1
        assert runtime.realised_profit > 0

        cancelled = next(
            oid
            for oid, (_side, price) in ladder(runtime).items()
            if price == Decimal(48000)
        )
        _cancel_from_outside(app, cancelled)

        runtime = app.runtime(bot_id)
        assert resting(app.urls) == ladder(runtime)
        assert sides_by_price(runtime)[Decimal(48000)] == "BUY"
        assert cancelled not in ladder(runtime)

        app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=SPOT))
        app.deliver()

        assert app.bot(bot_id).state is S.HALTED
        assert app.runtime(bot_id).reason is GridReason.SWITCH_OFF
        assert resting(app.urls) == {}


def test_a_bot_starts_from_a_closed_session_and_opens_it_itself(
    exchange: FakeExchange,
) -> None:
    """`EPIC-034C` — no Enable trading step: Start reconciles the account
    through the real `SessionReadiness`, opens the session and the user data
    stream, and lays the ladder."""
    with booted(exchange, open_session=False) as app:
        starts: list[str] = []
        app.stream.start = lambda: starts.append("start")  # type: ignore[method-assign]
        assert app.scope.session_state.enabled is False

        bot_id = _started(app)

        assert app.scope.session_state.enabled is True
        assert starts == ["start"]
        assert app.bot(bot_id).state is S.RUNNING
        assert resting(app.urls) == ladder(app.runtime(bot_id))


def _cancel_from_outside(app: BootedApp, client_order_id: str) -> None:
    """The user cancels one of the bot's orders on the exchange's website."""
    app.scope.ports.client_factory.create(OrderSubmissionMode.LIVE).cancel_order(
        SYMBOL, client_order_id
    )
    app.deliver()


def test_a_restart_reconciles_a_fill_missed_while_closed_without_a_duplicate(
    exchange: FakeExchange,
) -> None:
    """The app closes with the ladder resting; the 48,800 buy fills while it
    is closed, so no stream hears it. On the next boot the bot is RECOVERING
    and places nothing; trading on reconciles it from the exchange's history:
    the fill is counted, its sell placed once, and every level holds at most
    one order."""
    with booted(exchange) as first:
        bot_id = _started(first)
        bought_before = first.runtime(bot_id).inventory

    exchange.urls.spot_account.set_last_price(SYMBOL, Decimal(48700))
    exchange.urls.spot_account.drain_user_data_events()  # nobody was listening

    with booted(exchange) as second:
        assert second.bot(bot_id).state is S.RECOVERING
        posts_before = len(resting(second.urls))

        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=SPOT)
        )

        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.RUNNING
        assert resting(second.urls) == ladder(runtime)
        assert len(resting(second.urls)) == posts_before + 1
        prices = [price for _side, price in resting(second.urls).values()]
        assert len(prices) == len(set(prices))
        assert sides_by_price(runtime)[Decimal(49600)] == "SELL"
        assert runtime.inventory > bought_before
