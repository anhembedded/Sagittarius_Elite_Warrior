"""`EPIC-045G` - the host's "confirm this bot's resume" is the screen's own Confirm resume.

It adds no way to confirm: it dispatches `ConfirmBotResumeCommand`. What it adds is the real-money
answer (a mainnet bot needs its venue typed, as at the resume) and the words for a bot that holds no
proposal.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_resume_for_host import (
    ConfirmResumeForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ConfirmBotResumeForHostCommand,
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


class _Dispatcher(ICommandDispatcher):
    """Answers each confirmation with `answer` and remembers what it was given."""

    def __init__(self, answer: BotCommandResult) -> None:
        self.answer = answer
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert isinstance(input_dto, handler_class), "the key is the command's own type"
        self.dispatched.append(input_dto)
        return self.answer


def _store_with(venue: TradingVenue) -> FakeBotStore:
    store = FakeBotStore()
    bot = Bot(
        BotId("aaaaaa"),
        BotDefinition("grid one", "grid", venue, "BTCUSDT", {"lower": "60000"}),
        BotLifecycle(BotLifecycleState.HALTED),
        FAKE_CLOCK_START,
    )
    store.save(StoredBot(bot, {}))
    return store


def _handler(
    venue: TradingVenue, answer: BotCommandResult | None = None
) -> tuple[ConfirmResumeForHostCommandHandler, _Dispatcher]:
    dispatcher = _Dispatcher(answer or BotCommandResult.done("aaaaaa"))
    return ConfirmResumeForHostCommandHandler(
        _store_with(venue), dispatcher
    ), dispatcher


def test_confirming_for_the_host_is_the_confirmation_the_screen_dispatches() -> None:
    handler, dispatcher = _handler(TradingVenue.SPOT_TESTNET)

    result = handler.execute(ConfirmBotResumeForHostCommand("aaaaaa"))

    assert result.accepted
    assert dispatcher.dispatched == [ConfirmBotResumeCommand("aaaaaa")]
    assert "price moved" in result.message, (
        "the accepted words say the ladder may be refused"
    )


def test_a_mainnet_confirmation_is_not_dispatched_until_the_venue_is_typed() -> None:
    venue = TradingVenue.SPOT_MAINNET
    handler, dispatcher = _handler(venue)

    refused = handler.execute(ConfirmBotResumeForHostCommand("aaaaaa"))
    wrong = handler.execute(
        ConfirmBotResumeForHostCommand("aaaaaa", TradingVenue.SPOT_TESTNET.value)
    )

    assert refused.refusal is wrong.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert f"--confirm-venue {venue.value}" in refused.message
    assert dispatcher.dispatched == [], "a held proposal is never laid unconfirmed"


def test_a_mainnet_confirmation_with_its_venue_typed_is_dispatched() -> None:
    venue = TradingVenue.SPOT_MAINNET
    handler, dispatcher = _handler(venue)

    result = handler.execute(ConfirmBotResumeForHostCommand("aaaaaa", venue.value))

    assert result.accepted
    assert dispatcher.dispatched == [ConfirmBotResumeCommand("aaaaaa")]


def test_a_bot_that_holds_no_proposal_is_told_to_resume_first_and_to_wait() -> None:
    handler, _ = _handler(
        TradingVenue.SPOT_TESTNET,
        BotCommandResult.refused(
            BotRefusal.NO_RESUME_PROPOSAL, "press Resume", "aaaaaa"
        ),
    )

    result = handler.execute(ConfirmBotResumeForHostCommand("aaaaaa"))

    assert result.refusal is BotRefusal.NO_RESUME_PROPOSAL
    assert "`bot resume aaaaaa`" in result.message and "a few seconds" in result.message


def test_any_other_refusal_of_the_screen_reaches_the_operator_unchanged() -> None:
    refused = BotCommandResult.refused(
        BotRefusal.INVALID_TRANSITION, "the bot is RUNNING", "aaaaaa"
    )
    handler, _ = _handler(TradingVenue.SPOT_TESTNET, refused)

    assert handler.execute(ConfirmBotResumeForHostCommand("aaaaaa")) == refused


def test_confirming_a_bot_that_does_not_exist_is_refused_not_dispatched() -> None:
    dispatcher = _Dispatcher(BotCommandResult.done("zzzzzz"))

    result = ConfirmResumeForHostCommandHandler(FakeBotStore(), dispatcher).execute(
        ConfirmBotResumeForHostCommand("zzzzzz")
    )

    assert result.refusal is BotRefusal.NOT_FOUND
    assert dispatcher.dispatched == []
