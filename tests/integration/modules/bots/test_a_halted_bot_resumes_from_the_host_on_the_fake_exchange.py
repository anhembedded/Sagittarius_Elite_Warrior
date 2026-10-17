"""`EPIC-042E` - `run --resume-halted` on the composed app over the fake exchange.

@details A bot halted by an Emergency Stop has its order session closed and its ladder off the
exchange. The host's request is a person's Resume and Confirm answered in advance: the session
opens, the worker proposes the ladder, the host confirms it, and the bot is RUNNING with the
ladder resting. Only the user data stream's websocket start is stubbed, as in
`test_resume_opens_the_order_session_on_the_fake_exchange.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeHaltedForHostCommand,
    ResumeHaltedResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
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


def _halted_by_emergency_stop(app: BootedApp) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult) and created.bot_id is not None
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(started, BotCommandResult) and started.accepted, started
    app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=SPOT))
    app.deliver()
    assert app.bot(created.bot_id).state is S.HALTED
    return created.bot_id


def test_the_host_resumes_a_halted_bot_through_the_screens_resume_and_confirm(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        bot_id = _halted_by_emergency_stop(app)

        result = app.engine.dispatch(
            ResumeHaltedForHostCommand, ResumeHaltedForHostCommand(None)
        )
        app.deliver()

        assert isinstance(result, ResumeHaltedResult)
        (outcome,) = result.bots
        assert (outcome.bot_id, outcome.was, outcome.resumed) == (
            bot_id,
            "HALTED",
            True,
        )
        assert outcome.note == ""
        assert app.scope.session_state.enabled is True
        assert app.bot(bot_id).state is S.RUNNING
        assert resting(app.urls) == ladder(app.runtime(bot_id))


def test_a_stopped_bot_is_left_alone_by_the_hosts_resume(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        created = app.engine.dispatch(
            CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
        )
        assert isinstance(created, BotCommandResult) and created.bot_id is not None

        result = app.engine.dispatch(
            ResumeHaltedForHostCommand, ResumeHaltedForHostCommand(None)
        )

        assert isinstance(result, ResumeHaltedResult)
        assert result.bots == ()
        assert app.bot(created.bot_id).state is S.DRAFT
