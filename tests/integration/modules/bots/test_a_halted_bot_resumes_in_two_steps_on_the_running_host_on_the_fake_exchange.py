"""`EPIC-045G` - `bot resume` then `bot confirm-resume` on a HALTED bot, on the composed app over the fake exchange.

@details The owner's rule: what the Bots tab does at runtime the host can do. The tab's Resume proposes a
ladder and places nothing, a person reads it, and Confirm resume lays it. Here the operator's two command
files do the same through the host's own poller: the first leaves the bot HALTED with nothing resting, the
second lays the ladder and the bot is RUNNING. Only the user data stream's websocket start is stubbed.
"""

from __future__ import annotations

import re

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


def _fingerprint_of(message: str) -> str:
    found = re.search(r"Fingerprint ([0-9a-f]{8})", message)
    assert found is not None, message
    return found.group(1)


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
        fingerprint = _fingerprint_of(proposed.message)
        assert (
            "nothing is placed" in proposed.message
            and "orders from" in proposed.message
        )
        assert f"--proposal {fingerprint}" in proposed.message
        assert state_of(app.store, bot_id) is S.HALTED
        assert resting(app.urls) == {}, "a proposal places no order"

        confirmed = operator.ask(
            HostControlRequest(
                HostControlAction.CONFIRM_RESUME, bot_id, proposal=fingerprint
            )
        )
        app.deliver()

        assert confirmed.status is HostControlStatus.DONE, confirmed.message
        assert state_of(app.store, bot_id) is S.RUNNING
        assert resting(app.urls) == ladder(app.runtime(bot_id))


def test_a_confirmation_that_names_another_proposal_or_none_lays_nothing_and_the_right_one_still_does(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        bot_id = _halted(app)
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        fingerprint = _fingerprint_of(
            operator.ask(HostControlRequest(HostControlAction.RESUME, bot_id)).message
        )
        other = "0" * 8 if fingerprint != "0" * 8 else "f" * 8

        stale = operator.ask(
            HostControlRequest(HostControlAction.CONFIRM_RESUME, bot_id, proposal=other)
        )
        unnamed = operator.ask(
            HostControlRequest(HostControlAction.CONFIRM_RESUME, bot_id)
        )

        assert stale.status is HostControlStatus.REFUSED
        assert "proposal changed" in stale.message
        assert unnamed.status is HostControlStatus.REFUSED
        assert "--proposal <fingerprint>" in unnamed.message
        assert state_of(app.store, bot_id) is S.HALTED
        assert resting(app.urls) == {}, "neither refusal laid anything"

        good = operator.ask(
            HostControlRequest(
                HostControlAction.CONFIRM_RESUME, bot_id, proposal=fingerprint
            )
        )
        app.deliver()

        assert good.status is HostControlStatus.DONE, good.message
        assert state_of(app.store, bot_id) is S.RUNNING


def test_a_confirmation_with_no_proposal_is_refused_and_lays_nothing(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        bot_id = _halted(app)
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)

        refused = operator.ask(
            HostControlRequest(
                HostControlAction.CONFIRM_RESUME, bot_id, proposal="1a2b3c4d"
            )
        )

        assert refused.status is HostControlStatus.REFUSED
        assert f"`bot resume {bot_id}`" in refused.message
        assert state_of(app.store, bot_id) is S.HALTED
        assert resting(app.urls) == {}


def test_a_second_resume_after_a_refused_confirmation_gives_a_fingerprint_that_confirms(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review of #715: the retry the refusal tells the operator to make must end in a confirmable fingerprint."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        bot_id = _halted(app)
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        first = operator.ask(HostControlRequest(HostControlAction.RESUME, bot_id))
        wrong = operator.ask(
            HostControlRequest(
                HostControlAction.CONFIRM_RESUME, bot_id, proposal="0" * 8
            )
        )

        again = operator.ask(HostControlRequest(HostControlAction.RESUME, bot_id))
        confirmed = operator.ask(
            HostControlRequest(
                HostControlAction.CONFIRM_RESUME,
                bot_id,
                proposal=_fingerprint_of(again.message),
            )
        )
        app.deliver()

        assert first.status is again.status is HostControlStatus.DONE
        assert wrong.status is HostControlStatus.REFUSED
        assert confirmed.status is HostControlStatus.DONE, confirmed.message
        assert state_of(app.store, bot_id) is S.RUNNING
