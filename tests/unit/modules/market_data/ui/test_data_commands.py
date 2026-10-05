"""`EPIC-033D` — the Data mode's commands are actions, available while idle.

The commands the market-data module really contributes, bound by the real
presenter's `bind_commands` over its real view model.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_command_binding import (
    bind_data_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_commands import (
    DELETE_SELECTED,
    EXPORT,
    IMPORT,
    OPTIMIZE,
    PURGE_ALL,
    SCAN_ALL,
    SCAN_STATUS,
    SYNC_ALL_GAPS,
    SYNC_TIMEFRAME,
    data_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.database_screen import (
    DATABASE_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions

_REQUESTS = {
    SCAN_STATUS: "checkStatusRequested",
    SCAN_ALL: "checkAllStatusRequested",
    SYNC_TIMEFRAME: "syncRequested",
    SYNC_ALL_GAPS: "syncAllGapsRequested",
    EXPORT: "exportRequested",
    IMPORT: "importRequested",
    OPTIMIZE: "vacuumRequested",
    DELETE_SELECTED: "clearDataRequested",
    PURGE_ALL: "purgeAllRequested",
}


def _actions(view_model: DataManagementViewModel):
    return bound_actions(
        view_model,
        data_commands(DATABASE_ROUTE),
        lambda binder: bind_data_commands(binder, view_model),
    )


def test_the_market_data_module_contributes_every_data_command() -> None:
    modes = {
        command.command_id: command.mode
        for command in real_contributions(Mock()).commands()
    }

    for command_id in _REQUESTS:
        assert modes[command_id] == DATABASE_ROUTE


@pytest.mark.parametrize(("command_id", "signal_name"), _REQUESTS.items())
def test_each_action_makes_its_request(qapp, command_id, signal_name) -> None:
    view_model = DataManagementViewModel()
    actions = _actions(view_model)
    heard: list[bool] = []
    getattr(view_model, signal_name).connect(lambda *_args: heard.append(True))

    actions.action(command_id).trigger()

    assert heard == [True]


def test_the_commands_apply_only_while_the_mode_is_idle(qapp) -> None:
    view_model = DataManagementViewModel()
    actions = _actions(view_model)
    assert all(actions.action(command_id).isEnabled() for command_id in _REQUESTS)

    view_model.set_ui_mode("SYNCING")
    assert not any(actions.action(command_id).isEnabled() for command_id in _REQUESTS)

    view_model.set_ui_mode("IDLE")
    assert all(actions.action(command_id).isEnabled() for command_id in _REQUESTS)
