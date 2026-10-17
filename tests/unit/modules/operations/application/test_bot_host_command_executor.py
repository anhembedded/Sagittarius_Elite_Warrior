"""`EPIC-038J` - the host maps each action to the bots' contract command and nothing else."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    PauseBotForHostCommand,
    ResumeBotForHostCommand,
    StopBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.bot_host_command_executor import (
    BotHostCommandExecutor,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    BOT,
    command,
)


class _Dispatcher(ICommandDispatcher):
    def __init__(self, answer: BotCommandResult) -> None:
        self.answer = answer
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert isinstance(input_dto, handler_class), "the key is the command's own type"
        self.dispatched.append(input_dto)
        return self.answer


def test_each_action_dispatches_its_contract_command_and_only_that() -> None:
    dispatcher = _Dispatcher(BotCommandResult.done(BOT))
    executor = BotHostCommandExecutor(dispatcher)

    for action in HostControlAction:
        executor.execute(command(action=action, confirmed_venue="spot_mainnet"))

    assert dispatcher.dispatched == [
        StopBotForHostCommand(BOT),
        PauseBotForHostCommand(BOT),
        ResumeBotForHostCommand(BOT, "spot_mainnet"),
    ]


def test_an_accepted_stop_says_it_is_stopping_and_not_yet_stopped() -> None:
    executor = BotHostCommandExecutor(_Dispatcher(BotCommandResult.done(BOT)))

    outcome = executor.execute(command(action=HostControlAction.STOP))

    assert outcome.accepted
    assert "STOPPING" in outcome.message and "STOPPED" in outcome.message


def test_a_refusal_carries_the_bots_own_words() -> None:
    refused = BotCommandResult.refused(
        BotRefusal.INVALID_TRANSITION,
        "Bot 44wa1x is STOPPED; stop is not possible",
        BOT,
    )

    outcome = BotHostCommandExecutor(_Dispatcher(refused)).execute(command())

    assert not outcome.accepted
    assert outcome.message == "Bot 44wa1x is STOPPED; stop is not possible"
