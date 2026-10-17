"""`run --resume-halted`: the host gives the answers a person gives the Resume and its Confirm (`EPIC-042E`, D13).

The handler dispatches the screen's own commands, so these tests script the dispatcher and
read what was asked, in what order, with which real-money answer. The wait for the bot's
worker to propose the ladder runs on a fake clock that a fake pause moves.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_halted_for_host import (
    ResumeHaltedForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_halted_for_host.handler import (
    PROPOSAL_POLL_S,
    PROPOSAL_WAIT_S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    HaltedBotResumeOutcome,
    ResumeHaltedForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_waiter import (
    FakeBotWaiter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_monotonic_clock import (
    FakeMonotonicClock,
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
TESTNET = TradingVenue.SPOT_TESTNET
MAINNET = TradingVenue.SPOT_MAINNET


class _Screen(ICommandDispatcher):
    """The screen's two commands, scripted: what Resume answers and when a proposal appears."""

    def __init__(self) -> None:
        self.asked: list[object] = []
        self.refuse_resume: dict[str, str] = {}
        self.refuse_confirm: dict[str, str] = {}
        #: Confirm answers "no proposal" this many times before it is accepted.
        self.polls_before_proposal = 0
        self._polls = 0

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert isinstance(input_dto, handler_class)
        self.asked.append(input_dto)
        if isinstance(input_dto, ResumeBotCommand):
            reason = self.refuse_resume.get(input_dto.bot_id)
            if reason is not None:
                return BotCommandResult.refused(
                    BotRefusal.VENUE_NOT_READY, reason, input_dto.bot_id
                )
            return BotCommandResult.done(input_dto.bot_id)
        assert isinstance(input_dto, ConfirmBotResumeCommand)
        reason = self.refuse_confirm.get(input_dto.bot_id)
        if reason is not None:
            return BotCommandResult.refused(
                BotRefusal.INVALID_TRANSITION, reason, input_dto.bot_id
            )
        if self._polls < self.polls_before_proposal:
            self._polls += 1
            return BotCommandResult.refused(
                BotRefusal.NO_RESUME_PROPOSAL, "no proposal", input_dto.bot_id
            )
        self._polls = 0
        return BotCommandResult.done(input_dto.bot_id)


class _World:
    def __init__(self) -> None:
        self.store = FakeBotStore()
        self.screen = _Screen()
        self.clock = FakeMonotonicClock()
        self.waiter = FakeBotWaiter(self.clock)
        self.handler = ResumeHaltedForHostCommandHandler(
            self.store, self.screen, self.clock, self.waiter
        )

    def bot(self, bot_id: str, state: BotLifecycleState, venue: TradingVenue) -> None:
        bot = Bot(
            BotId(bot_id),
            BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"}),
            BotLifecycle(state),
            FAKE_CLOCK_START,
        )
        self.store.save(StoredBot(bot, {}))

    def resume(self, confirmed: str | None = None) -> list[HaltedBotResumeOutcome]:
        return list(self.handler.execute(ResumeHaltedForHostCommand(confirmed)).bots)


def test_only_a_halted_or_awaiting_bot_is_resumed_and_no_other_state_is_touched() -> (
    None
):
    world = _World()
    world.bot("aaaaaa", S.HALTED, TESTNET)
    world.bot("bbbbbb", S.AWAITING_RECOVERY, TESTNET)
    for bot_id, state in (
        ("cccccc", S.RUNNING),
        ("dddddd", S.PAUSED),
        ("eeeeee", S.RECOVERING),
        ("ffffff", S.STOPPED),
        ("gggggg", S.ERROR),
        ("hhhhhh", S.DRAFT),
    ):
        world.bot(bot_id, state, TESTNET)

    outcomes = world.resume()

    assert [(o.bot_id, o.was, o.resumed) for o in outcomes] == [
        ("aaaaaa", "HALTED", True),
        ("bbbbbb", "AWAITING_RECOVERY", True),
    ]
    assert {getattr(c, "bot_id") for c in world.screen.asked} == {"aaaaaa", "bbbbbb"}  # noqa: B009


def test_a_bot_is_resumed_then_confirmed_once_the_worker_has_proposed() -> None:
    world = _World()
    world.bot("aaaaaa", S.HALTED, TESTNET)
    world.screen.polls_before_proposal = 3

    (outcome,) = world.resume()

    assert outcome.resumed and outcome.note == ""
    assert world.screen.asked[0] == ResumeBotCommand(
        "aaaaaa", real_money_confirmed=False
    )
    assert [type(c) for c in world.screen.asked[1:]] == [ConfirmBotResumeCommand] * 4
    assert world.waiter.pauses == 3, (
        "it asks again after each pause, not before the first"
    )


def test_a_proposal_that_never_comes_leaves_the_bot_and_the_wait_is_bounded() -> None:
    world = _World()
    world.bot("aaaaaa", S.HALTED, TESTNET)
    world.screen.polls_before_proposal = 10**6

    (outcome,) = world.resume()

    assert not outcome.resumed
    assert "no resume proposal was ready" in outcome.note
    assert world.waiter.pauses == pytest.approx(
        PROPOSAL_WAIT_S / PROPOSAL_POLL_S, abs=1
    )


def test_a_mainnet_bot_is_resumed_only_when_the_operator_typed_its_venue() -> None:
    world = _World()
    world.bot("aaaaaa", S.HALTED, MAINNET)
    world.bot("bbbbbb", S.HALTED, TESTNET)

    skipped, resumed = world.resume(confirmed=None)

    assert not skipped.resumed
    assert "--confirm-venue spot_mainnet" in skipped.note
    assert resumed.resumed
    assert [getattr(c, "bot_id") for c in world.screen.asked] == ["bbbbbb", "bbbbbb"]  # noqa: B009


def test_a_typed_mainnet_venue_carries_the_real_money_answer_to_the_resume() -> None:
    world = _World()
    world.bot("aaaaaa", S.HALTED, MAINNET)

    (outcome,) = world.resume(confirmed=MAINNET.value)

    assert outcome.resumed
    assert world.screen.asked[0] == ResumeBotCommand(
        "aaaaaa", real_money_confirmed=True
    )


def test_another_venues_name_does_not_confirm_a_mainnet_bot() -> None:
    world = _World()
    world.bot("aaaaaa", S.HALTED, MAINNET)

    (outcome,) = world.resume(confirmed=TradingVenue.FUTURES_MAINNET.value)

    assert not outcome.resumed
    assert world.screen.asked == []


def test_a_refused_resume_is_reported_in_the_screens_words_and_nothing_is_confirmed() -> (
    None
):
    world = _World()
    world.bot("aaaaaa", S.HALTED, TESTNET)
    world.screen.refuse_resume["aaaaaa"] = (
        "the order session did not open: key rejected"
    )

    (outcome,) = world.resume()

    assert not outcome.resumed
    assert "the order session did not open: key rejected" in outcome.note
    assert [type(c) for c in world.screen.asked] == [ResumeBotCommand]


def test_a_refused_confirmation_is_reported_and_not_retried() -> None:
    world = _World()
    world.bot("aaaaaa", S.HALTED, TESTNET)
    world.screen.refuse_confirm["aaaaaa"] = "the bot is no longer HALTED"

    (outcome,) = world.resume()

    assert not outcome.resumed and "no longer HALTED" in outcome.note
    assert world.waiter.pauses == 0


def test_one_bots_refusal_does_not_stop_the_next() -> None:
    world = _World()
    world.bot("aaaaaa", S.HALTED, TESTNET)
    world.bot("bbbbbb", S.HALTED, TESTNET)
    world.screen.refuse_resume["aaaaaa"] = "blocked"

    first, second = world.resume()

    assert (first.resumed, second.resumed) == (False, True)


def test_a_futures_mainnet_bot_is_reported_closed_even_with_its_venue_typed() -> None:
    world = _World()
    world.bot("aaaaaa", S.HALTED, TradingVenue.FUTURES_MAINNET)

    (outcome,) = world.resume(confirmed=TradingVenue.FUTURES_MAINNET.value)

    assert not outcome.resumed
    assert world.screen.asked == []
    assert outcome.note
