"""`EPIC-039L` - Futures mainnet is open to bots, and real money is asked about on every path.

@details The owner opened Futures mainnet on 2026-10-17 (decision O2 of `EPIC-039L`): no lock
stands in front of it any more, and what stands in front of real money is the confirmation the
Spot mainnet path already asks for. Each path that could create, move, start or resume a bot
there is proven in the composed app over the Futures fake: creating a draft is accepted like
on the testnet (moving a draft to another venue is Spot-only and not in play); starting or resuming without the confirmation of real money is
refused in words (`REAL_MONEY_NOT_CONFIRMED`), as the headless host's start and resume are when
`--confirm-venue` is not typed. Nothing here reaches a real exchange, and no order is placed on
mainnet: the fake stands behind every venue.
"""

from __future__ import annotations

import pytest
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
from .futures_fake_exchange import SYMBOL
from .grid_fake_exchange import FakeExchange

MAINNET = TradingVenue.FUTURES_MAINNET
_CLOSED = "closed to bots"


def _stored(
    app: BootedFuturesBots, state: BotLifecycleState, bot_id: str = "cafe01"
) -> str:
    """A bot already on disk for Futures mainnet: a plan file or an older file puts one there."""
    bot = Bot(
        BotId(bot_id),
        BotDefinition("mainnet", "grid", MAINNET, SYMBOL, GRID),
        BotLifecycle(state),
        FAKE_CLOCK_START,
    )
    app.store.save(StoredBot(bot, {}))
    return bot_id


def _result(value: object) -> BotCommandResult:
    assert isinstance(value, BotCommandResult)
    return value


def _asks_for_real_money(result: object) -> BotCommandResult:
    answer = _result(result)
    assert not answer.accepted, (
        "a mainnet bot started or resumed without the confirmation"
    )
    assert answer.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED, answer.message
    assert _CLOSED not in answer.message
    return answer


def test_creating_a_bot_on_futures_mainnet_is_accepted_like_on_the_testnet(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        result = _result(
            app.engine.dispatch(
                CreateBotCommand, CreateBotCommand("x", "grid", MAINNET, SYMBOL, GRID)
            )
        )

        assert result.accepted, result.message
        assert result.bot_id is not None
        assert app.bot(result.bot_id).definition.venue is MAINNET


def test_starting_a_futures_mainnet_bot_without_the_real_money_confirmation_is_refused(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.STOPPED)

        result = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))

        _asks_for_real_money(result)
        assert app.bot(bot_id).state is BotLifecycleState.STOPPED
        assert app.resting() == {}


def test_the_hosts_start_without_the_venue_typed_says_to_type_it(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.STOPPED)

        result = app.engine.dispatch(
            StartBotForHostCommand, StartBotForHostCommand(bot_id)
        )

        answer = _asks_for_real_money(result)
        assert f"--confirm-venue {MAINNET.value}" in answer.message
        assert app.bot(bot_id).state is BotLifecycleState.STOPPED


def test_the_hosts_start_with_a_wrong_venue_typed_is_refused(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.STOPPED)

        result = app.engine.dispatch(
            StartBotForHostCommand,
            StartBotForHostCommand(bot_id, TradingVenue.FUTURES_TESTNET.value),
        )

        _asks_for_real_money(result)


def test_the_hosts_start_with_the_venue_typed_is_no_longer_stopped_by_a_lock(
    futures: FakeExchange,
) -> None:
    """With `--confirm-venue futures_mainnet` the start goes on to the readiness every start
    answers to; whatever it says (the fake has no mainnet key here), it is not a lock's words."""
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.STOPPED)

        result = _result(
            app.engine.dispatch(
                StartBotForHostCommand, StartBotForHostCommand(bot_id, MAINNET.value)
            )
        )

        assert result.refusal is not BotRefusal.REAL_MONEY_NOT_CONFIRMED
        assert _CLOSED not in result.message


def test_resuming_a_halted_futures_mainnet_bot_without_the_confirmation_is_refused(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.HALTED)

        result = app.engine.dispatch(ResumeBotCommand, ResumeBotCommand(bot_id))

        _asks_for_real_money(result)
        assert app.bot(bot_id).state is BotLifecycleState.HALTED


def test_resuming_a_recovering_futures_mainnet_bot_without_the_confirmation_is_refused(
    futures: FakeExchange,
) -> None:
    """The desktop's way out of RECOVERING reopens the order session as a Resume from HALTED does."""
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.RECOVERING)

        result = app.engine.dispatch(ResumeBotCommand, ResumeBotCommand(bot_id))

        _asks_for_real_money(result)
        assert app.bot(bot_id).state is BotLifecycleState.RECOVERING


def test_the_hosts_resume_recovering_asks_for_the_venue_to_be_typed(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _stored(app, BotLifecycleState.RECOVERING)

        result = app.engine.dispatch(
            ResumeRecoveringForHostCommand, ResumeRecoveringForHostCommand(None)
        )

        assert isinstance(result, ResumeRecoveringResult)
        (outcome,) = result.venues
        assert not outcome.opened and bot_id in outcome.bot_ids
        assert f"--confirm-venue {MAINNET.value}" in outcome.note
        assert app.bot(bot_id).state is BotLifecycleState.RECOVERING


@pytest.mark.parametrize("typed", [None, MAINNET.value])
def test_the_hosts_resume_recovering_never_says_the_venue_is_closed(
    futures: FakeExchange, typed: str | None
) -> None:
    with booted_futures_bots(futures) as app:
        _stored(app, BotLifecycleState.RECOVERING)

        result = app.engine.dispatch(
            ResumeRecoveringForHostCommand, ResumeRecoveringForHostCommand(typed)
        )

        assert isinstance(result, ResumeRecoveringResult)
        (outcome,) = result.venues
        assert _CLOSED not in outcome.note
