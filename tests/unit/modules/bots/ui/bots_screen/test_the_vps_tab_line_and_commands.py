"""`EPIC-047E` - the VPS tab's line above the screen, its own command ids, and the link starting only when it is shown."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_line import HostLine
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    NEW_BOT,
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import BotsView
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.first_shown import (
    FirstShown,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.host_line_bar import (
    HostLineBar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.vps_command_ids import (
    VPS_COMMAND_PREFIX,
    vps_command_id,
    vps_commands,
)


def test_the_bots_tab_shows_no_line(qtbot: QtBot) -> None:
    view = BotsView()
    qtbot.addWidget(view)
    view.show()

    assert view.host_line.isHidden()


def test_a_down_link_is_a_warning_and_a_live_one_is_information(qtbot: QtBot) -> None:
    lines = [HostLine("up", True)]
    bar = HostLineBar()
    qtbot.addWidget(bar)

    bar.show_line_of(lambda: lines[0])
    assert bar.text == "up"
    up_kind = bar.kind

    lines[0] = HostLine("disconnected, data as of 12:00", False)
    bar.draw_line()

    assert bar.text == "disconnected, data as of 12:00"
    assert bar.kind != up_kind


def test_the_line_is_asked_again_on_its_own(qtbot: QtBot) -> None:
    asked: list[int] = []
    bar = HostLineBar()
    qtbot.addWidget(bar)

    bar.show_line_of(lambda: HostLine(str(asked.append(1) or len(asked)), True))

    qtbot.waitUntil(lambda: len(asked) >= 2, timeout=3000)


def test_the_vps_commands_are_the_bots_commands_under_their_own_ids() -> None:
    bots = [command.command_id for command in bots_commands("bots")]
    vps = [command.command_id for command in vps_commands("vps_bots")]

    assert len(vps) == len(set(vps))
    assert not set(vps) & set(bots)
    assert vps == [vps_command_id(command_id) for command_id in bots]
    assert all(command_id.startswith(VPS_COMMAND_PREFIX) for command_id in vps)
    assert vps_command_id(NEW_BOT) == f"{VPS_COMMAND_PREFIX}.new_bot"
    assert {command.mode for command in vps_commands("vps_bots")} == {"vps_bots"}


def test_something_runs_once_on_the_first_show_and_not_before(qtbot: QtBot) -> None:
    calls: list[int] = []
    widget = QWidget()
    qtbot.addWidget(widget)
    FirstShown(widget, lambda: calls.append(1))
    assert calls == []

    widget.show()
    widget.hide()
    widget.show()

    assert calls == [1]
