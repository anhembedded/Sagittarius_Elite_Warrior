"""`EPIC-045G` - `bot resume` then `bot confirm-resume` on a HALTED bot, on the composed app over the fake exchange.

@details The owner's rule: what the Bots tab does at runtime the host can do. The tab's Resume proposes a
ladder and places nothing, a person reads it, and Confirm resume lays it. Here the operator's two command
files do the same through the host's own poller: the first leaves the bot HALTED with nothing resting, the
second lays the ladder and the bot is RUNNING. Only the user data stream's websocket start is stubbed.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
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
from .host_control_world import create_grid_bot, operator_of, state_of

S = BotLifecycleState


def _halted(app: BootedApp) -> str:
    bot_id = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
    assert isinstance(started, BotCommandResult) and started.accepted, started
    app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=SPOT))
    app.deliver()
    assert state_of(app.store, bot_id) is S.HALTED
    return bot_id


def test_a_resume_proposes_and_places_nothing_and_the_confirmation_lays_the_ladder(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        bot_id = _halted(app)
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)

        proposed = operator.ask(HostControlRequest(HostControlAction.RESUME, bot_id))

        assert proposed.status is HostControlStatus.DONE, proposed.message
        assert "nothing is placed" in proposed.message
        assert f"`bot confirm-resume {bot_id}`" in proposed.message
        assert state_of(app.store, bot_id) is S.HALTED
        assert resting(app.urls) == {}, "a proposal places no order"

        confirmed = operator.ask(
            HostControlRequest(HostControlAction.CONFIRM_RESUME, bot_id)
        )
        app.deliver()

        assert confirmed.status is HostControlStatus.DONE, confirmed.message
        assert state_of(app.store, bot_id) is S.RUNNING
        assert resting(app.urls) == ladder(app.runtime(bot_id))


def test_a_confirmation_with_no_proposal_is_refused_and_lays_nothing(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        bot_id = _halted(app)
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)

        refused = operator.ask(
            HostControlRequest(HostControlAction.CONFIRM_RESUME, bot_id)
        )

        assert refused.status is HostControlStatus.REFUSED
        assert f"`bot resume {bot_id}`" in refused.message
        assert state_of(app.store, bot_id) is S.HALTED
        assert resting(app.urls) == {}
