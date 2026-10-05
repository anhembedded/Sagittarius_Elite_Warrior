"""`EPIC-033F` — the real window's one Output pane carries every screen's log.

Built by the shared `main_window` fixture from the real modules' screens. The
four log cards (Dev Board's System monitor, each desk's log, Data's sync log,
Backtest's run log) are channels of the pane now, and a line a screen's view
model logs is what the pane shows on that channel.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import OutputPane


def _pane(main_window) -> OutputPane:
    pane = main_window.findChild(OutputPane, "workbench::output")
    assert pane is not None
    return pane


def test_every_screen_log_is_a_channel_of_the_one_pane(
    qtbot, main_window, app_engine
) -> None:
    """A desk keeps a log only when its venue is enabled in this run; a
    disabled desk builds no view model and offers no channel."""
    qtbot.addWidget(main_window)
    enabled = app_engine.context.container.resolve(IVenueTradingPorts).enabled()
    desks = {desk_profile_for(venue).title for venue in enabled}
    pane = _pane(main_window)
    choice = pane.findChild(QComboBox, "workbench::output::channel")
    assert choice is not None

    titles = {choice.itemText(index) for index in range(choice.count())}

    assert titles == {"Market", "System monitor", "Sync", "Backtest", *desks}
    assert len(main_window.findChildren(OutputPane)) == 1


def test_a_line_the_data_screen_logs_is_shown_on_its_channel(
    qtbot, main_window
) -> None:
    qtbot.addWidget(main_window)
    pane = _pane(main_window)

    main_window.switch_screen("data_management")
    main_window.presenters["data_management"]._view_model.logModel.append(
        "sync finished"
    )

    current = pane.current_channel
    assert current is not None
    assert current.channel_id == "data.sync"
    assert "sync finished" in pane.copy_lines()
