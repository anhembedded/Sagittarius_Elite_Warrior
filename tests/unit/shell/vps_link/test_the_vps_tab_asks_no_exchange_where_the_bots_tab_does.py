"""`EPIC-047E` (AC10, charter O1) - beside the Bots tab, which reads the exchange for a selected bot, the VPS tab reads none.

The business promise: the same screen classes, given the same fake exchange, make exchange reads in one tab and none in the
other, because every fact in the VPS tab comes from the host. The Bots tab's reads are the control: without them a silent
VPS tab would prove nothing.
"""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.bots_screen.bots_screen_fixtures import (
    BotsScreen,
    open_screen,
    stored,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import BTC
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_screen import (
    open_vps_screen,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import VpsTabWorld


def _exchange_reads(screen: BotsScreen) -> int:
    return (
        len(screen.market_sources.asked)
        + len(screen.account.symbols_read)
        + len(screen.mainnet_account.symbols_read)
    )


def test_the_bots_tab_reads_the_exchange_and_the_vps_tab_does_not(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    (tmp_path / "bots").mkdir()
    (tmp_path / "vps").mkdir()
    bots = open_screen(
        tmp_path / "bots", qtbot, [stored("a00001", BotLifecycleState.DRAFT)]
    )
    bots.settle()
    bots.view.model.select_requested.emit("a00001")
    bots.settle()

    vps = open_vps_screen(tmp_path / "vps", qtbot, tab)
    vps.screen.settle()
    vps.screen.view.model.select_requested.emit(BTC.bot_id)
    vps.screen.settle()

    assert vps.screen.view.model.selected is not None
    assert vps.screen.view.model.selected.bot_id == BTC.bot_id
    assert _exchange_reads(bots) > 0
    assert _exchange_reads(vps.screen) == 0
