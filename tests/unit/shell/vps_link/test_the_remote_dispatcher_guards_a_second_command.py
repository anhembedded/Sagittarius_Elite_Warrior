"""`EPIC-047E` (AC6, decision 7) - a bot is held to one command at a time, and a lost command blocks the next that could be applied twice.

The business promise: a command whose outcome is not known (the link was cut while it waited) is not followed by a second
that would apply the first twice; the verbs that only reduce exposure (Stop, Pause) are never the ones withheld; and two
presses within the host's wait cannot both reach it.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import HostControlAction
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_command_dispatcher import (
    IN_FLIGHT_WORDS,
    RemoteCommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import (
    ETH,
    BlockingDoor,
    build_dispatcher,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import (
    VpsHost,
    VpsTabWorld,
)


def _a_lost_start_then_back_up() -> tuple[
    VpsTabWorld, BlockingDoor, RemoteCommandDispatcher
]:
    host = VpsHost()
    door = BlockingDoor()
    host.door = door
    tab = VpsTabWorld(host).start()
    dispatcher, _ = build_dispatcher(tab)
    first = threading.Thread(
        target=lambda: dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))
    )
    first.start()
    assert door.arrived.wait(timeout=5)
    tab.cut()
    first.join(timeout=10)
    tab.wait_up()
    door.release.set()
    return tab, door, dispatcher


def test_stop_and_pause_pass_the_block_of_a_lost_command_the_other_verbs_do_not() -> (
    None
):
    tab, door, dispatcher = _a_lost_start_then_back_up()

    stop = dispatcher.dispatch(
        StopBotCommand, StopBotCommand(ETH.bot_id, ExposureHandling.KEEP)
    )
    pause = dispatcher.dispatch(PauseBotCommand, PauseBotCommand(ETH.bot_id))
    start = dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))
    edit = dispatcher.dispatch(
        EditBotCommand, EditBotCommand(ETH.bot_id, ETH.name, {"grid_count": "9"})
    )
    tab.stop()

    assert stop.accepted and pause.accepted  # type: ignore[attr-defined]
    assert not start.accepted and not edit.accepted  # type: ignore[attr-defined]
    assert [s[1].action for s in door.sent] == [
        HostControlAction.START,
        HostControlAction.STOP,
        HostControlAction.PAUSE,
    ]


def test_a_second_command_on_a_bot_while_one_waits_for_the_host_is_refused() -> None:
    host = VpsHost()
    door = BlockingDoor()
    host.door = door
    tab = VpsTabWorld(host).start()
    dispatcher, _ = build_dispatcher(tab)
    first = threading.Thread(
        target=lambda: dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))
    )
    first.start()
    assert door.arrived.wait(timeout=5)

    second = dispatcher.dispatch(ResumeBotCommand, ResumeBotCommand(ETH.bot_id))
    door.release.set()
    first.join(timeout=10)
    after = dispatcher.dispatch(ResumeBotCommand, ResumeBotCommand(ETH.bot_id))
    tab.stop()

    assert not second.accepted  # type: ignore[attr-defined]
    assert second.message == IN_FLIGHT_WORDS  # type: ignore[attr-defined]
    assert after.accepted  # type: ignore[attr-defined]
    assert [s[1].action for s in door.sent] == [
        HostControlAction.START,
        HostControlAction.RESUME,
    ]


def test_a_second_start_on_a_bot_whose_first_was_lost_is_refused_with_the_request_id() -> (
    None
):
    tab, door, dispatcher = _a_lost_start_then_back_up()

    again = dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))
    tab.stop()

    assert not again.accepted  # type: ignore[attr-defined]
    assert door.sent[0][0] in again.message  # type: ignore[attr-defined]
    assert len(door.sent) == 1
