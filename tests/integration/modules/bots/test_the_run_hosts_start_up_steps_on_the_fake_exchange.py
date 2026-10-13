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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_steps import (
    ResumeRecoveringBots,
    StartPlannedBots,
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

        StartPlannedBots(_Plan(planned), _dispatcher(app), None).run()

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
