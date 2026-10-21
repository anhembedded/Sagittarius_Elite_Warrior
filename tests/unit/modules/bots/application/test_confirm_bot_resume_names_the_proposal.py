"""`EPIC-045G` (owner decision O3) - the screen's Confirm resume, with and without a named proposal.

The Bots tab names none, as before: one person sees and confirms. The host names the fingerprint a person
read, and a held proposal that is another one is refused in words before anything is queued.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
    ConfirmBotResumeCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.proposal_runner_world import (
    PROPOSAL,
    ProposalRunner,
)


def _handler(runner: ProposalRunner) -> ConfirmBotResumeCommandHandler:
    store = FakeBotStore()
    bot = Bot(
        BotId("aaaaaa"),
        BotDefinition(
            "grid", "grid", TradingVenue.SPOT_TESTNET, "BTCUSDT", {"lower": "1"}
        ),
        BotLifecycle(BotLifecycleState.HALTED),
        FAKE_CLOCK_START,
    )
    store.save(StoredBot(bot, {}))
    return ConfirmBotResumeCommandHandler(store, runner)


def test_the_tabs_confirmation_names_no_proposal_and_confirms_whichever_is_held() -> (
    None
):
    runner = ProposalRunner()

    result = _handler(runner).execute(ConfirmBotResumeCommand("aaaaaa"))

    assert result.accepted
    assert runner.confirmed == [("aaaaaa", None)]


def test_a_confirmation_that_names_the_held_proposal_is_queued_with_its_name() -> None:
    runner = ProposalRunner()

    result = _handler(runner).execute(
        ConfirmBotResumeCommand("aaaaaa", PROPOSAL.fingerprint)
    )

    assert result.accepted
    assert runner.confirmed == [("aaaaaa", PROPOSAL.fingerprint)], (
        "the worker compares it again"
    )


def test_a_confirmation_that_names_another_proposal_is_refused_and_queues_nothing() -> (
    None
):
    runner = ProposalRunner()

    result = _handler(runner).execute(ConfirmBotResumeCommand("aaaaaa", "deadbeef"))

    assert result.refusal is BotRefusal.RESUME_PROPOSAL_CHANGED
    assert f"{PROPOSAL.orders} orders from {PROPOSAL.price}" in result.message
    assert PROPOSAL.fingerprint not in result.message, (
        "the new name is read from a new resume"
    )
    assert runner.confirmed == []


def test_no_held_proposal_is_still_refused_as_before() -> None:
    runner = ProposalRunner(proposal=None)

    result = _handler(runner).execute(ConfirmBotResumeCommand("aaaaaa", "deadbeef"))

    assert result.refusal is BotRefusal.NO_RESUME_PROPOSAL
    assert runner.confirmed == []
