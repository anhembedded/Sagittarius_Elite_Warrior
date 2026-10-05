"""`BUG-134` regression — `DevBoardPanel._open_strategy_params_dialog()`
passed `self` (a `QObject`, not a `QWidget` since `EPIC-025` PR 1.4c-3) as
the new `StrategyParamsDialog`'s Qt parent. `Overlay(QDialog)` requires a
`QWidget | None` parent, so every click raised `TypeError` before any
dialog could show — 100% reproducible, never caught because nothing
exercised the button end to end.

`BOT-144` moved the method onto `StrategyCard` (`dev_board_widgets/
strategy_card.py`), which parents to its own `self.window()` instead —
still never the `DevBoardPanel`/`QObject` this regression was about, so the
call site below follows the method, the assertion does not change.
`EPIC-033P` moved the card to `desk/strategy_card/strategy_card.py`; the patch
follows the dialog's name there.

`StrategyParamsDialog` is patched here — its real `.exec()` is modal, and
this suite runs under `QT_QPA_PLATFORM=offscreen` with no human to dismiss
it (the exact shape `BUG-048`/`test_app_bootstrapper_exception_handler.py`
warns about); a hanging regression test is worse than a failing one.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_panel import (
    DevBoardPanel,
)

#: Where the card reads the dialog: `EPIC-033P` moved the card to the desks
#: and its import to the top of its module.
_DIALOG_PATH = (
    "Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.strategy_card."
    "strategy_card.StrategyParamsDialog"
)


@pytest.fixture
def view_model(qapp):
    return DashboardQmlViewModel()


@pytest.fixture
def panel(qapp, view_model, request):
    controls = DevBoardPanel(view_model)
    host = QWidget()
    layout = QVBoxLayout(host)
    for _title, card in controls.dock_panels:
        layout.addWidget(card)
    host.resize(380, 700)
    host.show()
    qapp.processEvents()
    request.addfinalizer(host.deleteLater)
    return controls


def test_open_strategy_params_dialog_does_not_crash(qapp, panel):
    """Was `TypeError: 'QDialog.__init__' called with wrong argument
    types` — `DevBoardPanel` is a `QObject`, not a `QWidget`, and cannot
    itself be a `QDialog`'s parent."""
    with patch(_DIALOG_PATH) as dialog_cls:
        panel._strategy_card._open_strategy_params_dialog()  # must not raise

    dialog_cls.assert_called_once()
    parent = dialog_cls.call_args[0][1]
    assert parent is not panel  # this is exactly what used to crash
