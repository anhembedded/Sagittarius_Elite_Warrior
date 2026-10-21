"""`EPIC-038J` - the host's "pause this bot" and "resume this bot" are the screen's own commands.

Like Stop and Start for the host (`test_host_bot_requests.py`), these two add no way to pause
or resume: they dispatch `PauseBotCommand` and `ResumeBotCommand`. A HALTED bot is not resumed
from here - its resume proposes a ladder that a person reads and confirms (decision D13) - and
a RECOVERING bot on a mainnet venue is resumed only when the operator typed the venue (O8).
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot_for_host import (
    PauseBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot_for_host import (
    ResumeBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    PauseBotForHostCommand,
    ResumeBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
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

S = BotLifecycleState


class _RecordingDispatcher(ICommandDispatcher):
    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert isinstance(input_dto, handler_class), "the key is the command's own type"
        self.dispatched.append(input_dto)
        return BotCommandResult.done(getattr(input_dto, "bot_id"))  # noqa: B009 - both name a bot


def _store_with(state: BotLifecycleState, venue: TradingVenue) -> FakeBotStore:
    store = FakeBotStore()
    bot = Bot(
        BotId("aaaaaa"),
        BotDefinition("grid one", "grid", venue, "BTCUSDT", {"lower": "60000"}),
        BotLifecycle(state),
        FAKE_CLOCK_START,
    )
    store.save(StoredBot(bot, {}))
    return store


def test_pausing_for_the_host_is_the_pause_the_screen_dispatches() -> None:
    dispatcher = _RecordingDispatcher()

    result = PauseBotForHostCommandHandler(dispatcher).execute(
        PauseBotForHostCommand("aaaaaa")
    )

    assert result.accepted
    assert dispatcher.dispatched == [PauseBotCommand("aaaaaa")]


@pytest.mark.parametrize("state", [S.PAUSED, S.RECOVERING])
def test_resuming_a_paused_or_recovering_testnet_bot_is_the_screens_resume(
    state: BotLifecycleState,
) -> None:
    dispatcher = _RecordingDispatcher()
    handler = ResumeBotForHostCommandHandler(
        _store_with(state, TradingVenue.SPOT_TESTNET), dispatcher
    )

    result = handler.execute(ResumeBotForHostCommand("aaaaaa"))

    assert result.accepted
    assert dispatcher.dispatched == [ResumeBotCommand("aaaaaa")]


@pytest.mark.parametrize("state", [S.HALTED, S.AWAITING_RECOVERY])
def test_resuming_a_halted_bot_proposes_and_the_words_name_the_second_step(
    state: BotLifecycleState,
) -> None:
    dispatcher = _RecordingDispatcher()
    handler = ResumeBotForHostCommandHandler(
        _store_with(state, TradingVenue.SPOT_TESTNET), dispatcher
    )

    result = handler.execute(ResumeBotForHostCommand("aaaaaa"))

    assert result.accepted
    assert dispatcher.dispatched == [ResumeBotCommand("aaaaaa")]
    assert "nothing is placed" in result.message
    assert "`bot confirm-resume aaaaaa`" in result.message
    assert "--confirm-venue" not in result.message


@pytest.mark.parametrize("state", [S.HALTED, S.AWAITING_RECOVERY, S.RECOVERING])
def test_a_mainnet_resume_that_reopens_the_session_is_not_dispatched_until_the_venue_is_typed(
    state: BotLifecycleState,
) -> None:
    venue = TradingVenue.SPOT_MAINNET
    dispatcher = _RecordingDispatcher()
    handler = ResumeBotForHostCommandHandler(_store_with(state, venue), dispatcher)

    refused = handler.execute(ResumeBotForHostCommand("aaaaaa"))

    assert refused.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert dispatcher.dispatched == []


def test_a_mainnet_proposal_names_the_flag_the_confirmation_needs() -> None:
    venue = TradingVenue.SPOT_MAINNET
    handler = ResumeBotForHostCommandHandler(
        _store_with(S.HALTED, venue), _RecordingDispatcher()
    )

    result = handler.execute(ResumeBotForHostCommand("aaaaaa", venue.value))

    assert result.accepted
    assert (
        f"`bot confirm-resume aaaaaa --confirm-venue {venue.value}`" in result.message
    )


def test_a_refused_proposal_is_the_screens_refusal_not_a_proposal_reply() -> None:
    class _Refusing(_RecordingDispatcher):
        def dispatch(
            self, handler_class: type, input_dto: object | None = None
        ) -> object:
            return BotCommandResult.refused(
                BotRefusal.INVALID_DEFINITION, "Resume is blocked: x", "aaaaaa"
            )

    result = ResumeBotForHostCommandHandler(
        _store_with(S.HALTED, TradingVenue.SPOT_TESTNET), _Refusing()
    ).execute(ResumeBotForHostCommand("aaaaaa"))

    assert not result.accepted and "Resume is blocked" in result.message


def test_a_recovering_mainnet_bot_is_not_resumed_until_the_venue_is_typed() -> None:
    venue = TradingVenue.SPOT_MAINNET
    dispatcher = _RecordingDispatcher()
    handler = ResumeBotForHostCommandHandler(
        _store_with(S.RECOVERING, venue), dispatcher
    )

    refused = handler.execute(ResumeBotForHostCommand("aaaaaa"))
    wrong = handler.execute(
        ResumeBotForHostCommand("aaaaaa", TradingVenue.SPOT_TESTNET.value)
    )

    assert refused.refusal is wrong.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert f"--confirm-venue {venue.value}" in refused.message
    assert dispatcher.dispatched == []


def test_a_recovering_mainnet_bot_with_its_venue_typed_carries_the_real_money_answer() -> (
    None
):
    venue = TradingVenue.SPOT_MAINNET
    dispatcher = _RecordingDispatcher()
    handler = ResumeBotForHostCommandHandler(
        _store_with(S.RECOVERING, venue), dispatcher
    )

    result = handler.execute(ResumeBotForHostCommand("aaaaaa", venue.value))

    assert result.accepted
    assert dispatcher.dispatched == [
        ResumeBotCommand("aaaaaa", real_money_confirmed=True)
    ]


def test_a_paused_mainnet_bot_resumes_without_the_venue_because_no_session_is_reopened() -> (
    None
):
    dispatcher = _RecordingDispatcher()
    handler = ResumeBotForHostCommandHandler(
        _store_with(S.PAUSED, TradingVenue.SPOT_MAINNET), dispatcher
    )

    result = handler.execute(ResumeBotForHostCommand("aaaaaa"))

    assert result.accepted
    assert dispatcher.dispatched == [ResumeBotCommand("aaaaaa")]


def test_resuming_a_bot_that_does_not_exist_is_refused_not_dispatched() -> None:
    dispatcher = _RecordingDispatcher()

    result = ResumeBotForHostCommandHandler(FakeBotStore(), dispatcher).execute(
        ResumeBotForHostCommand("zzzzzz")
    )

    assert result.refusal is BotRefusal.NOT_FOUND
    assert dispatcher.dispatched == []
