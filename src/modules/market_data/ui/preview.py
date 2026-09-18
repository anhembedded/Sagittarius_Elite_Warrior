from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view import (
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view_model import (
    DataManagementViewModel,
)

#: `scripts/preview_qml.py::discover_previews()` keys a preview by its parent
#: directory name, which is `ui` for every `modules/<name>/ui/preview.py` at
#: a module's own root — this override is what keeps the screen addressable
#: as `data_management` (its route, `module.py`'s own `route = "data_management"`)
#: rather than colliding on `ui` the moment a second module puts a
#: `preview.py` there. `EPIC-025` PR 4.4b, moved from `screens/data_management/`.
PREVIEW_KEY = "data_management"


def build_preview() -> QWidget:
    """Builds a standalone preview for the Data Management screen (EPIC-005E — QtWidgets)."""
    view_model = DataManagementViewModel()
    view_model.status_model.upsert_row(
        "BTCUSDT", "2024-01-01 00:00", "2024-06-01 00:00", "216,000", "OK"
    )
    view_model.status_model.upsert_row(
        "ETHUSDT",
        "2024-01-01 00:00",
        "2024-05-15 08:00",
        "198,400",
        "3 gaps found!",
    )
    view_model.log_model.append("Checking database status for BTCUSDT (1m)...")
    view_model.log_model.append("Scan complete.", level="success")
    view_model.set_stats("414,400", "128.40 MB")
    view_model.useCustomTime = True

    view = DataManagementView()
    view.set_view_model(view_model)
    view.resize(1400, 820)
    return view
