"""`EPIC-038J` - the host maps each action to the bots' contract command and nothing else."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    LOSS_CAP_SUBJECT,
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    AcknowledgeLossCapForHostCommand,
    AddBotForHostCommand,
    DeleteBotForHostCommand,
    EditBotForHostCommand,
    PauseBotForHostCommand,
    ResumeBotForHostCommand,
    StartBotForHostCommand,
    StopBotForOperatorCommand,
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


_ENTRY = NewBotEntry("sol grid", "grid", "spot_testnet", "SOLUSDT")


def test_each_action_dispatches_its_contract_command_and_only_that() -> None:
    dispatcher = _Dispatcher(BotCommandResult.done(BOT))
    executor = BotHostCommandExecutor(dispatcher)

    for action in HostControlAction:
        executor.execute(
            command(
                action=action,
                confirmed_venue="spot_mainnet",
                settings=(ParameterSetting("lower", "81000"),),
                entry=_ENTRY,
            )
        )

    assert dispatcher.dispatched == [
        StopBotForOperatorCommand(BOT, "spot_mainnet"),
        PauseBotForHostCommand(BOT),
        ResumeBotForHostCommand(BOT, "spot_mainnet"),
        StartBotForHostCommand(BOT, "spot_mainnet"),
        EditBotForHostCommand(BOT, (ParameterSetting("lower", "81000"),)),
        AddBotForHostCommand(_ENTRY),
        DeleteBotForHostCommand(BOT),
        AcknowledgeLossCapForHostCommand(),
    ]


def test_a_stop_file_that_closes_the_position_dispatches_the_close() -> None:
    dispatcher = _Dispatcher(BotCommandResult.done(BOT))

    BotHostCommandExecutor(dispatcher).execute(command(close_position=True))

    assert dispatcher.dispatched == [
        StopBotForOperatorCommand(BOT, None, close_position=True)
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


def test_an_accepted_start_says_the_bot_is_starting() -> None:
    executor = BotHostCommandExecutor(_Dispatcher(BotCommandResult.done(BOT)))

    outcome = executor.execute(command(action=HostControlAction.START))

    assert outcome.accepted and "STARTING" in outcome.message


def test_an_accepted_edit_speaks_the_hosts_own_sentence_naming_what_changed() -> None:
    said = BotCommandResult(accepted=True, bot_id=BOT, message="lower 81305 -> 81000.")
    executor = BotHostCommandExecutor(_Dispatcher(said))

    outcome = executor.execute(
        command(
            action=HostControlAction.EDIT,
            settings=(ParameterSetting("lower", "81000"),),
        )
    )

    assert outcome.accepted and outcome.message == "lower 81305 -> 81000."


def test_an_accepted_edit_without_a_sentence_still_says_the_bot_is_draft() -> None:
    executor = BotHostCommandExecutor(_Dispatcher(BotCommandResult.done(BOT)))

    outcome = executor.execute(
        command(
            action=HostControlAction.EDIT,
            settings=(ParameterSetting("lower", "81000"),),
        )
    )

    assert outcome.accepted and "DRAFT" in outcome.message


def test_only_an_edit_an_add_and_a_delete_speak_the_hosts_own_sentence_every_other_action_keeps_its_fixed_words() -> (
    None
):
    said = BotCommandResult(accepted=True, bot_id=BOT, message="something else")
    executor = BotHostCommandExecutor(_Dispatcher(said))

    outcome = executor.execute(command(action=HostControlAction.START))

    assert outcome.message == "the bot is STARTING (see `bot show`)"


def test_an_accepted_acknowledgement_says_bots_may_start_again_and_the_day_keeps_counting() -> (
    None
):
    executor = BotHostCommandExecutor(
        _Dispatcher(BotCommandResult.done(LOSS_CAP_SUBJECT))
    )

    outcome = executor.execute(
        command(action=HostControlAction.ACKNOWLEDGE_LOSS_CAP, bot_id=LOSS_CAP_SUBJECT)
    )

    assert outcome.accepted
    assert "start again" in outcome.message and "00:00 UTC" in outcome.message


def test_an_acknowledgement_of_a_cap_that_is_not_tripped_is_refused_in_the_caps_words() -> (
    None
):
    refused = BotCommandResult.refused(
        BotRefusal.LOSS_CAP_NOT_TRIPPED, "the loss cap is not tripped", LOSS_CAP_SUBJECT
    )

    outcome = BotHostCommandExecutor(_Dispatcher(refused)).execute(
        command(action=HostControlAction.ACKNOWLEDGE_LOSS_CAP, bot_id=LOSS_CAP_SUBJECT)
    )

    assert not outcome.accepted and outcome.message == "the loss cap is not tripped"


def test_an_accepted_add_speaks_the_hosts_sentence_naming_the_new_id() -> None:
    said = BotCommandResult(
        accepted=True, bot_id="x03yij", message="bot x03yij was created"
    )
    executor = BotHostCommandExecutor(_Dispatcher(said))

    outcome = executor.execute(
        command(action=HostControlAction.ADD, bot_id="new-bot", entry=_ENTRY)
    )

    assert outcome.accepted and outcome.message == "bot x03yij was created"
    assert outcome.bot_id == "x03yij", "the operator gets the id the host chose"


def test_only_an_add_carries_a_bot_id_back() -> None:
    executor = BotHostCommandExecutor(_Dispatcher(BotCommandResult.done(BOT)))

    outcome = executor.execute(command(action=HostControlAction.DELETE))

    assert outcome.bot_id == ""


def test_an_accepted_delete_without_a_sentence_still_says_the_bot_was_deleted() -> None:
    executor = BotHostCommandExecutor(_Dispatcher(BotCommandResult.done(BOT)))

    outcome = executor.execute(command(action=HostControlAction.DELETE))

    assert outcome.accepted and "deleted" in outcome.message


def test_a_refused_delete_carries_the_bots_own_words() -> None:
    refused = BotCommandResult.refused(
        BotRefusal.EXPOSURE_LEFT, "Bot 44wa1x is kept: its record holds 0.5", BOT
    )

    outcome = BotHostCommandExecutor(_Dispatcher(refused)).execute(
        command(action=HostControlAction.DELETE)
    )

    assert not outcome.accepted
    assert outcome.message == "Bot 44wa1x is kept: its record holds 0.5"
