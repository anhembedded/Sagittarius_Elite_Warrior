"""What the `run` host asks of the bots, and that it asks the same thing the screen does (`EPIC-038D`).

`operations` may import only the bots' `contracts/`, so the host's two requests
- stop this bot, start this bot - are contracts that the bots module answers by
dispatching the commands the Bots tab dispatches (`StopBotCommand`,
`StartBotCommand`). These tests record that dispatch: the host adds no way to
start or stop a bot, and a mainnet start carries the real-money answer only when
the operator typed the venue (decision O8).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot_for_host import (
    StartBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot_for_host import (
    StopBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StartBotForHostCommand,
    StopBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
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


class _RecordingDispatcher(ICommandDispatcher):
    """Answers every command accepted and keeps what it was asked."""

    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert isinstance(input_dto, handler_class), "the key is the command's own type"
        self.dispatched.append(input_dto)
        bot_id = getattr(input_dto, "bot_id")  # noqa: B009 - both commands name a bot
        return BotCommandResult.done(bot_id)


def _store_with(bot_id: str, venue: TradingVenue) -> FakeBotStore:
    store = FakeBotStore()
    bot = Bot(
        BotId(bot_id),
        BotDefinition("grid one", "grid", venue, "BTCUSDT", {"lower": "60000"}),
        BotLifecycle(BotLifecycleState.STOPPED),
        FAKE_CLOCK_START,
    )
    store.save(StoredBot(bot, {}))
    return store


def test_stopping_for_the_host_is_the_stop_the_screen_dispatches_keeping_the_base() -> (
    None
):
    dispatcher = _RecordingDispatcher()

    result = StopBotForHostCommandHandler(dispatcher).execute(
        StopBotForHostCommand("aaaaaa")
    )

    assert result.accepted
    assert dispatcher.dispatched == [StopBotCommand("aaaaaa", ExposureHandling.KEEP)]


def test_stopping_for_the_host_with_a_close_dispatches_the_close_at_market() -> None:
    """`BUG-224`: the exposure handling on the command is the one the screen's Stop receives."""
    dispatcher = _RecordingDispatcher()

    StopBotForHostCommandHandler(dispatcher).execute(
        StopBotForHostCommand("aaaaaa", ExposureHandling.CLOSE_AT_MARKET)
    )

    assert dispatcher.dispatched == [
        StopBotCommand("aaaaaa", ExposureHandling.CLOSE_AT_MARKET)
    ]


def test_starting_a_testnet_bot_for_the_host_asks_for_no_real_money_answer() -> None:
    dispatcher = _RecordingDispatcher()
    handler = StartBotForHostCommandHandler(
        _store_with("aaaaaa", TradingVenue.SPOT_TESTNET), dispatcher
    )

    result = handler.execute(StartBotForHostCommand("aaaaaa"))

    assert result.accepted
    assert dispatcher.dispatched == [StartBotCommand("aaaaaa")]


def test_a_mainnet_start_without_the_venue_typed_is_refused_and_dispatches_nothing() -> (
    None
):
    """Spot mainnet is the example; Futures mainnet asks the same question
    (`test_futures_mainnet_asks_for_the_real_money_confirmation_on_every_path.py`)."""
    venue = TradingVenue.SPOT_MAINNET
    dispatcher = _RecordingDispatcher()
    handler = StartBotForHostCommandHandler(_store_with("aaaaaa", venue), dispatcher)

    result = handler.execute(StartBotForHostCommand("aaaaaa"))

    assert not result.accepted
    assert result.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert f"--confirm-venue {venue.value}" in result.message
    assert dispatcher.dispatched == []


def test_a_mainnet_start_with_another_venue_typed_is_refused() -> None:
    """A command copied from a testnet run cannot start mainnet (decision O8)."""
    dispatcher = _RecordingDispatcher()
    handler = StartBotForHostCommandHandler(
        _store_with("aaaaaa", TradingVenue.SPOT_MAINNET), dispatcher
    )

    result = handler.execute(
        StartBotForHostCommand("aaaaaa", TradingVenue.SPOT_TESTNET.value)
    )

    assert result.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert dispatcher.dispatched == []


def test_a_mainnet_start_with_its_own_venue_typed_carries_the_real_money_answer() -> (
    None
):
    dispatcher = _RecordingDispatcher()
    handler = StartBotForHostCommandHandler(
        _store_with("aaaaaa", TradingVenue.SPOT_MAINNET), dispatcher
    )

    result = handler.execute(
        StartBotForHostCommand("aaaaaa", TradingVenue.SPOT_MAINNET.value)
    )

    assert result.accepted
    assert dispatcher.dispatched == [
        StartBotCommand("aaaaaa", real_money_confirmed=True)
    ]


def test_starting_a_bot_that_does_not_exist_is_refused_not_dispatched() -> None:
    dispatcher = _RecordingDispatcher()
    handler = StartBotForHostCommandHandler(FakeBotStore(), dispatcher)

    result = handler.execute(StartBotForHostCommand("zzzzzz"))

    assert result.refusal is BotRefusal.NOT_FOUND
    assert dispatcher.dispatched == []
