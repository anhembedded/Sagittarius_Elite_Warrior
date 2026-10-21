"""`EPIC-038D` - the host's start-up steps drive real bots on the fake Binance server.

  · `--start-planned`: a planned bot at rest is started by the Start the screen
    dispatches, and its ladder rests on the exchange;
  · `--resume-recovering` (decision O2): after a restart a bot is RECOVERING and stays so
    until the venue's order session opens - the step opens it the way the first deliberate
    action does, and the bot reconciles from the exchange's history.

The websocket is the one substitution (the fake speaks REST only), as in every journey here.
Nothing reaches a real exchange.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.planned_bot_not_started_event import (
    PlannedBotNotStartedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_steps import (
    ResumeRecoveringBots,
    StartPlannedBots,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.integration.golden.fakes.recording_event_publisher import (
    RecordingEventPublisher,
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
)

S = BotLifecycleState


class _Plan(IBotPlan):
    def __init__(self, *bot_ids: str) -> None:
        self._ids = frozenset(bot_ids)

    def exists(self) -> bool:
        return True

    def problem(self) -> str | None:
        return None

    def wants_running(self) -> frozenset[str]:
        return self._ids


def _dispatcher(app: BootedApp) -> ICommandDispatcher:
    return app.engine.container.resolve(ICommandDispatcher)  # type: ignore[type-abstract, no-any-return]


def _created(app: BootedApp) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    return created.bot_id


def test_start_planned_starts_a_planned_bot_at_rest_and_leaves_an_unplanned_one(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        planned = _created(app)
        unplanned = _created(app)
        assert app.bot(planned).state is S.DRAFT

        StartPlannedBots(
            _Plan(planned), _dispatcher(app), None, RecordingEventPublisher()
        ).run()

        assert app.bot(planned).state is S.RUNNING
        assert resting(app.urls) == ladder(app.runtime(planned)) != {}
        assert app.bot(unplanned).state is S.DRAFT


def test_resume_recovering_opens_the_order_session_and_the_bot_reconciles(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as first:
        started = first.engine.dispatch(
            StartBotCommand, StartBotCommand(_created(first))
        )
        assert isinstance(started, BotCommandResult)
        bot_id = started.bot_id
        assert bot_id is not None

    exchange.urls.spot_account.set_last_price(
        SYMBOL, Decimal(48700)
    )  # a buy fills while closed
    exchange.urls.spot_account.drain_user_data_events()

    with booted(exchange, open_session=False) as second:
        second.stream.start = lambda: None  # type: ignore[method-assign]  # the fake has no websocket
        assert second.bot(bot_id).state is S.RECOVERING
        assert second.scope.session_state.enabled is False

        ResumeRecoveringBots(_dispatcher(second), None).run()

        assert second.scope.session_state.enabled is True
        assert second.bot(bot_id).state is S.RUNNING
        assert resting(second.urls) == ladder(second.runtime(bot_id))


def test_start_planned_skips_an_unconfirmed_mainnet_bot_tells_it_and_starts_the_rest(
    exchange: FakeExchange,
) -> None:
    """`EPIC-045F`: the VPS case. One planned mainnet bot the unit does not confirm no longer
    stops the run: the testnet bot starts, the mainnet bot stays at rest, and one event names
    the command that starts it."""
    with booted(exchange) as app:
        testnet = _created(app)
        created = app.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("real", "grid", TradingVenue.SPOT_MAINNET, SYMBOL, GRID),
        )
        assert isinstance(created, BotCommandResult) and created.bot_id is not None
        mainnet = created.bot_id
        events = RecordingEventPublisher()

        StartPlannedBots(_Plan(testnet, mainnet), _dispatcher(app), None, events).run()

        assert app.bot(testnet).state is S.RUNNING
        assert app.bot(mainnet).state is S.DRAFT, (
            "no real-money bot started unconfirmed"
        )
        [event] = events.events
        assert isinstance(event, PlannedBotNotStartedEvent)
        assert (event.bot_id, event.venue) == (mainnet, "spot_mainnet")
        assert "was not confirmed" in event.reason


def test_start_planned_with_nothing_startable_is_not_fatal_and_tells_each_skipped_bot(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        first = app.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("a", "grid", TradingVenue.SPOT_MAINNET, SYMBOL, GRID),
        )
        assert isinstance(first, BotCommandResult) and first.bot_id is not None
        events = RecordingEventPublisher()

        StartPlannedBots(_Plan(first.bot_id), _dispatcher(app), None, events).run()

        assert app.bot(first.bot_id).state is S.DRAFT
        assert len(events.events) == 1


def test_start_planned_does_not_skip_the_mainnet_bot_whose_venue_the_run_confirmed(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        created = app.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("real", "grid", TradingVenue.SPOT_MAINNET, SYMBOL, GRID),
        )
        assert isinstance(created, BotCommandResult) and created.bot_id is not None
        events = RecordingEventPublisher()

        StartPlannedBots(
            _Plan(created.bot_id), _dispatcher(app), "spot_mainnet", events
        ).run()

        assert events.events == [], "a confirmed venue is not skipped"
