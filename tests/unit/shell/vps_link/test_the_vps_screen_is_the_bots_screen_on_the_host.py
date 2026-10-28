"""`EPIC-047E` (AC1, AC3, AC4, AC7) - the VPS tab is the Bots screen's own classes with the host behind its doors.

The business promise: the tab lists the bots the host published, a lifecycle command from its menu reaches the host's own gate
as the request the `bot` verb sends, and what the host cannot do from here (a new bot, a backtest) is off with its reason, not
hidden. The commands carry ids of their own, so the Bots tab beside it is not touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen import vps_backend
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    BACKTEST_TAB,
    NEW_BOT,
    lifecycle_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import BotsView
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.typed_venue_consent import (
    TypedVenueConsent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.vps_backend import (
    NO_NEW_BOT_HERE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.vps_command_ids import (
    vps_command_id,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.bots_screen.bots_answers import (
    Answers,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import (
    BTC,
    ETH,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_screen import (
    open_vps_screen,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import VpsTabWorld


def _names(view: BotsView) -> list[str]:
    return [str(view.bots.index(row, 0).data()) for row in range(view.bots.rowCount())]


def test_the_list_is_what_the_host_published(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    vps = open_vps_screen(tmp_path, qtbot, tab)
    vps.screen.settle()

    names = _names(vps.screen.view)

    assert BTC.name in names
    assert ETH.name in names


def test_the_line_above_the_tab_names_the_host_and_says_it_is_connected(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    vps = open_vps_screen(tmp_path, qtbot, tab)

    line = vps.screen.view.host_line

    assert "nathan-warrior" in line.text
    assert "connected" in line.text


def test_new_bot_is_off_with_its_reason_not_hidden(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    vps = open_vps_screen(tmp_path, qtbot, tab)

    new_bot = vps.actions.action(vps_command_id(NEW_BOT))

    assert not new_bot.isEnabled()
    assert vps.screen.view.model.new_bot_unavailable == NO_NEW_BOT_HERE


def test_the_backtest_tab_is_off_and_says_why(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    vps = open_vps_screen(tmp_path, qtbot, tab)
    vps.screen.settle()
    vps.screen.view.model.select_requested.emit(BTC.bot_id)
    vps.screen.settle()

    assert not vps.actions.action(vps_command_id(BACKTEST_TAB)).isEnabled()


def test_delete_from_the_menu_reaches_the_hosts_gate_as_the_delete_verb(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    vps = open_vps_screen(tmp_path, qtbot, tab, Answers(delete=True))
    vps.screen.settle()
    vps.screen.view.model.select_requested.emit(ETH.bot_id)
    vps.screen.settle()

    vps.actions.action(vps_command_id(lifecycle_id(BotAction.DELETE))).trigger()
    vps.screen.settle()

    (_, request, _) = tab.host.door.sent[0]
    assert request.action is HostControlAction.DELETE
    assert request.bot_id == ETH.bot_id


def test_the_link_starts_when_the_tab_is_first_shown_and_not_when_it_is_built(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    vps = open_vps_screen(tmp_path, qtbot, tab)
    assert vps.tab.opened_count == 0

    vps.screen.view.show()
    vps.screen.view.hide()
    vps.screen.view.show()

    assert vps.tab.opened_count == 1


def test_the_vps_screen_asks_the_real_money_question_by_typing_every_time(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[tuple[TradingVenue, str]] = []

    def typing(venue: TradingVenue, action: str) -> str | None:
        asked.append((venue, action))
        return venue.confirmation_word

    monkeypatch.setattr(vps_backend, "ask_typed_venue", typing)
    vps = open_vps_screen(tmp_path, qtbot, tab)
    consent = vps.backend.dependencies.consent

    assert isinstance(consent, TypedVenueConsent)
    assert consent.confirmed(TradingVenue.FUTURES_MAINNET, "start this bot")
    assert consent.confirmed(TradingVenue.FUTURES_MAINNET, "start this bot")
    assert len(asked) == 2


def test_new_bot_requested_by_another_way_still_reads_no_symbols(
    tab: VpsTabWorld, tmp_path: Path, qtbot: QtBot
) -> None:
    vps = open_vps_screen(tmp_path, qtbot, tab)
    vps.screen.settle()

    vps.screen.view.model.new_bot_requested.emit()
    vps.screen.settle()

    assert vps.screen.answers.asked == []
    assert vps.screen.market_sources.asked == []
