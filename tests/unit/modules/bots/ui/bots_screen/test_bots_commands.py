"""`EPIC-033D` — the Bots mode's commands are actions.

The commands the bots module really contributes, bound by
`bind_bots_commands` over a real `BotsViewModel`: each lifecycle command
follows its action's rule and the in-flight lock, and asks for that action
as its button did.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from PySide6.QtCore import QObject
from PySide6.QtGui import QKeySequence
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    ActionAvailability,
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_command_binding import (
    bind_bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    NEW_BOT,
    REFRESH_FILLS,
    bots_commands,
    lifecycle_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions


def _actions(view_model: BotsViewModel):
    return bound_actions(
        QObject(),
        bots_commands(BOTS_ROUTE),
        lambda binder: bind_bots_commands(binder, view_model),
    )


def test_the_bots_module_contributes_every_bots_command() -> None:
    modes = {
        command.command_id: command.mode
        for command in real_contributions(Mock()).commands()
    }

    for command_id in (NEW_BOT, REFRESH_FILLS, *map(lifecycle_id, BotAction)):
        assert modes[command_id] == BOTS_ROUTE


def test_a_lifecycle_command_follows_its_rule_and_asks_for_its_action(qapp) -> None:
    view_model = BotsViewModel()
    actions = _actions(view_model)
    start = actions.action(lifecycle_id(BotAction.START))
    asked: list[str] = []
    view_model.action_requested.connect(asked.append)
    assert not start.isEnabled()

    view_model.set_availability({BotAction.START: ActionAvailability(True, "")})
    start.trigger()

    assert start.isEnabled()
    assert asked == [BotAction.START.value]
    assert not actions.action(lifecycle_id(BotAction.STOP)).isEnabled()


def test_an_action_in_flight_disables_every_command(qapp) -> None:
    view_model = BotsViewModel()
    actions = _actions(view_model)
    view_model.set_availability({BotAction.START: ActionAvailability(True, "")})

    view_model.set_action_in_flight(True)

    assert not actions.action(NEW_BOT).isEnabled()
    assert not actions.action(lifecycle_id(BotAction.START)).isEnabled()

    view_model.set_action_in_flight(False)

    assert actions.action(NEW_BOT).isEnabled()
    assert actions.action(lifecycle_id(BotAction.START)).isEnabled()


def test_refresh_fills_waits_for_a_selected_bot(qapp) -> None:
    """The fills are the selected bot's; with none selected the read would do
    nothing (the PR #350 review)."""
    view_model = BotsViewModel()
    actions = _actions(view_model)
    refresh = actions.action(REFRESH_FILLS)
    assert not refresh.isEnabled()

    view_model.set_selected(
        BotSnapshot(
            "a00001",
            "g",
            "grid",
            TradingVenue.SPOT_TESTNET,
            "BTCUSDT",
            BotLifecycleState.DRAFT,
            datetime(2026, 10, 4, tzinfo=UTC),
            None,
        )
    )

    assert refresh.isEnabled()


def test_save_bot_is_the_platform_save(qapp) -> None:
    """HLD §11.2.3: Save bot is Ctrl+S, through `QKeySequence.Save`."""
    actions = _actions(BotsViewModel())

    assert actions.action(lifecycle_id(BotAction.SAVE)).shortcut() == QKeySequence(
        QKeySequence.StandardKey.Save
    )
