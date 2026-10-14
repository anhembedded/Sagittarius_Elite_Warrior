"""`BUG-202` — a bot halted by a switch-off resumes: Resume opens the order session.

@details The order session closes by Emergency Stop and opens by a deliberate action
(`EPIC-034C`). Start was one; Resume was not, so the budget the resume proposal
registers was refused (`TRADING_SWITCH_OFF`), the bot stayed HALTED saying "the order
session is not open", and the screen reported the command as done. Here the real
resume path runs on the composed app over the fake exchange, as in
`test_grid_bot_against_fake_server.py`; only the user data stream's websocket start is
stubbed, the one call the fake does not speak.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
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
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(started, BotCommandResult)
    assert started.accepted, started.message
    app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=SPOT))
    app.deliver()
    assert app.bot(created.bot_id).state is S.HALTED
    assert app.scope.session_state.enabled is False
    return created.bot_id


def test_resume_of_a_bot_halted_by_emergency_stop_opens_the_session_and_proposes(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        starts: list[str] = []
        app.stream.start = lambda: starts.append("start")  # type: ignore[method-assign]
        bot_id = _halted_by_emergency_stop(app)
        runner = app.engine.context.container.resolve(IBotRunner)

        resumed = app.engine.dispatch(ResumeBotCommand, ResumeBotCommand(bot_id))

        assert isinstance(resumed, BotCommandResult)
        assert resumed.accepted, resumed.message
        assert app.scope.session_state.enabled is True
        assert starts == ["start"]
        assert runner.has_resume_proposal(bot_id), app.runtime(bot_id).reason_detail

        confirmed = app.engine.dispatch(
            ConfirmBotResumeCommand, ConfirmBotResumeCommand(bot_id)
        )

        assert isinstance(confirmed, BotCommandResult)
        assert confirmed.accepted, confirmed.message
        assert app.bot(bot_id).state is S.RUNNING
        assert resting(app.urls) == ladder(app.runtime(bot_id))
