"""`EPIC-039H` - Futures mainnet stays closed to bots on every path until `EPIC-039L` (review of #490).

@details Flipping `BOT_MARKETS` makes a Futures Grid a thing the application can run. Real money is
the owner's to open (`EPIC-039` O7: a stop on the exchange for every position, then a testnet
soak), so the picker not listing the venue is not enough: each path that could create, move, start
or resume a bot there refuses it in words, in the composed app, before anything is asked of the
exchange. The headless host's `run --start-planned --confirm-venue futures_mainnet` is one of them.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
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
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeHaltedForHostCommand,
    ResumeHaltedResult,
    ResumeRecoveringForHostCommand,
    ResumeRecoveringResult,
    StartBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .futures_bots_world import GRID, BootedFuturesBots, booted_futures_bots
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange

MAINNET = TradingVenue.FUTURES_MAINNET
_CLOSED = "closed to bots"


def _stored(
    app: BootedFuturesBots, state: BotLifecycleState, bot_id: str = "cafe01"
) -> str:
    """A bot already on disk for the closed venue: a plan file or an older file puts one there."""
    bot = Bot(
        BotId(bot_id),
        BotDefinition("mainnet", "grid", MAINNET, SYMBOL, GRID),
        BotLifecycle(state),
        FAKE_CLOCK_START,
    )
    app.store.save(StoredBot(bot, {}))
    return bot_id


def _refused(result: object) -> BotCommandResult:
    assert isinstance(result, BotCommandResult)
    assert not result.accepted, "a closed venue accepted a bot"
    assert _CLOSED in result.message, result.message
    return result


def test_creating_a_bot_on_futures_mainnet_is_refused(futures: FakeExchange) -> None:
    with booted_futures_bots(futures) as app:
        result = app.engine.dispatch(
            CreateBotCommand, CreateBotCommand("x", "grid", MAINNET, SYMBOL, GRID)
        )

        assert _refused(result).refusal is BotRefusal.VENUE_NOT_READY
        assert app.store.load_all().bots == ()


def test_moving_a_draft_to_futures_mainnet_is_refused(futures: FakeExchange) -> None:
    with booted_futures_bots(futures) as app:
        created = app.engine.dispatch(
            CreateBotCommand, CreateBotCommand("x", "grid", FUTURES, SYMBOL, GRID)
        )
        assert isinstance(created, BotCommandResult) and created.bot_id

        result = app.engine.dispatch(
            ChangeBotVenueCommand, ChangeBotVenueCommand(created.bot_id, MAINNET)
        )

        _refused(result)
        assert app.bot(created.bot_id).definition.venue is FUTURES


def test_starting_a_stored_futures_mainnet_bot_is_refused_even_with_real_money_confirmed(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.STOPPED)

        result = app.engine.dispatch(
            StartBotCommand, StartBotCommand(bot_id, real_money_confirmed=True)
        )

        _refused(result)
        assert app.bot(bot_id).state is BotLifecycleState.STOPPED
        assert app.resting() == {}


def test_the_headless_hosts_start_planned_with_the_venue_typed_is_refused(
    futures: FakeExchange,
) -> None:
    """`run --start-planned --confirm-venue futures_mainnet`: the operator's typed answer to the
    real-money question is no answer to this one."""
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.STOPPED)

        result = app.engine.dispatch(
            StartBotForHostCommand, StartBotForHostCommand(bot_id, MAINNET.value)
        )

        _refused(result)
        assert app.bot(bot_id).state is BotLifecycleState.STOPPED


def test_the_hosts_start_without_the_venue_typed_says_closed_not_confirm(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.STOPPED)

        result = app.engine.dispatch(
            StartBotForHostCommand, StartBotForHostCommand(bot_id)
        )

        _refused(result)


def test_resuming_a_halted_futures_mainnet_bot_is_refused(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.HALTED)

        result = app.engine.dispatch(ResumeBotCommand, ResumeBotCommand(bot_id))

        _refused(result)
        assert app.bot(bot_id).state is BotLifecycleState.HALTED


@pytest.mark.parametrize("typed", [None, MAINNET.value])
def test_the_hosts_resume_halted_leaves_a_futures_mainnet_bot_halted(
    futures: FakeExchange, typed: str | None
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.HALTED)

        result = app.engine.dispatch(
            ResumeHaltedForHostCommand, ResumeHaltedForHostCommand(typed)
        )

        assert isinstance(result, ResumeHaltedResult)
        (outcome,) = result.bots
        assert not outcome.resumed and outcome.bot_id == bot_id
        assert _CLOSED in outcome.note
        assert app.bot(bot_id).state is BotLifecycleState.HALTED


@pytest.mark.parametrize("typed", [None, MAINNET.value])
def test_the_hosts_resume_recovering_leaves_a_futures_mainnet_bot_unopened(
    futures: FakeExchange, typed: str | None
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.RECOVERING)

        result = app.engine.dispatch(
            ResumeRecoveringForHostCommand, ResumeRecoveringForHostCommand(typed)
        )

        assert isinstance(result, ResumeRecoveringResult)
        (outcome,) = result.venues
        assert not outcome.opened and bot_id in outcome.bot_ids
        assert _CLOSED in outcome.note
        assert app.bot(bot_id).state is BotLifecycleState.RECOVERING
