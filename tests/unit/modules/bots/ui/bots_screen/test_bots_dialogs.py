"""`EPIC-029F` — Stop keeps the base unless told otherwise (O3); New bot needs
a typed symbol and an enabled Spot venue."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from PySide6.QtWidgets import QPushButton
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_dialog import (
    CREATE_BUTTON_TEXT,
    NO_SPOT_VENUE,
    NewBotDialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.stop_bot_dialog import (
    STOP_BUTTON_TEXT,
    StopBotDialog,
    stop_question,
)

from .bots_screen_fixtures import VENUE, stored

_RUNNING = BotSnapshot.of(stored("a00001", BotLifecycleState.RUNNING).bot)


def test_stop_preselects_keeping_the_base_and_says_orders_are_cancelled(qtbot) -> None:
    dialog = StopBotDialog(_RUNNING)
    qtbot.addWidget(dialog)

    assert dialog.choice() is BaseHandling.KEEP
    assert "cancelled at the exchange" in stop_question(_RUNNING)
    dialog.sell.setChecked(True)
    assert dialog.choice() is BaseHandling.SELL_AT_MARKET
    assert dialog.findChild(QPushButton, "btnConfirmStop").text() == STOP_BUTTON_TEXT


def test_stop_names_the_base_the_run_holds(qtbot) -> None:
    progress = BotProgress(Decimal(0), 0, 0, Decimal("0.0031"), Decimal(64000), "", "")
    holding = replace(_RUNNING, progress=progress)

    assert "It holds 0.0031 BTCUSDT base." in stop_question(holding)
    assert "no base" in stop_question(_RUNNING)


def test_create_waits_for_a_symbol_and_names_what_it_does(qtbot) -> None:
    dialog = NewBotDialog(["grid"], [VENUE])
    qtbot.addWidget(dialog)

    assert dialog.create_button.text() == CREATE_BUTTON_TEXT
    assert not dialog.create_button.isEnabled()
    qtbot.keyClicks(dialog.symbol, "ethusdt")
    assert dialog.create_button.isEnabled()

    command = dialog.command()
    assert (command.kind, command.venue, command.symbol) == ("grid", VENUE, "ETHUSDT")
    assert command.name == "ETHUSDT grid"
    assert command.config["grid_count"] == "10"


def test_without_an_enabled_spot_venue_nothing_can_be_created(qtbot) -> None:
    dialog = NewBotDialog(["grid"], [])
    qtbot.addWidget(dialog)
    qtbot.keyClicks(dialog.symbol, "BTCUSDT")

    assert not dialog.create_button.isEnabled()
    assert dialog.problem.text() == NO_SPOT_VENUE
