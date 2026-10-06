"""The Data mode in the booted app: a real Data → Sync history… drives its
presenter into SYNCING.

The Dev Board's boot-and-walkthrough tests left with it (`EPIC-033P` stage
3); the mode bar and every mode's build are `test_workbench_conformance.py`'s
and `test_main_window_state.py`'s.
"""

import os

from PySide6.QtGui import QAction

# Force offscreen rendering for headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_commands import (
    SYNC_HISTORY,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_widgets.shard_dialogs import (
    ShardChoice,
    SyncChoice,
)

# app_engine/main_window come from conftest.py, the one fixture to keep
# correct; it writes to a tmp_path copy of user_config.json, so a test that
# saves (Tools → Options' Apply, since `EPIC-033E`) never overwrites the real
# config.


def test_sanity_data_management_sync(qtbot, main_window, navigate, qapp, monkeypatch):
    """
    The Data mode loads through the router, and a real Data → Sync history…
    (its dialog answered) drives the presenter's FSM into SYNCING.
    """
    qtbot.addWidget(main_window)

    data_mgt_cfg = navigate("data_management")
    assert data_mgt_cfg is not None
    view = data_mgt_cfg["view_instance"]
    assert view is not None
    qapp.processEvents()

    presenter = data_mgt_cfg["presenter_instance"]

    # Ensure starting mode is IDLE
    assert presenter.fsm.current_state.value == "IDLE"

    # The user runs Data → Sync history… and syncs BTCUSDT 1m (`EPIC-033J`).
    monkeypatch.setattr(
        view,
        "ask_sync_history",
        lambda *_args: SyncChoice(ShardChoice("BTCUSDT", "1m"), None, None),
    )
    main_window.findChild(QAction, f"action::{SYNC_HISTORY}").trigger()

    qtbot.waitUntil(
        lambda: presenter.fsm.current_state.value == "SYNCING", timeout=2000
    )
