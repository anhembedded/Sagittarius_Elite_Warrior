from __future__ import annotations

from datetime import UTC, datetime

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
    """The Data mode (`EPIC-033J`) with two stored shards, one with gaps, its
    gaps listed in the Gaps panel and the counts in the status bar's words."""
    view_model = DataManagementViewModel()
    view_model.status_model.upsert_row(
        "BTCUSDT",
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 6, 1, tzinfo=UTC),
        216_000,
        "OK",
    )
    view_model.status_model.upsert_row(
        "ETHUSDT",
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 5, 15, 8, tzinfo=UTC),
        198_400,
        "3 gaps found!",
        "1h",
    )
    view_model.log_model.append("Checking database status for BTCUSDT (1m)...")
    view_model.log_model.append("Scan complete.", level="success")
    view_model.set_stats("414,400", "128.40 MB")

    view = DataManagementView()
    view.set_view_model(view_model)
    view_model.set_gap_inspector_data(
        "ETHUSDT",
        "1h",
        2,
        42,
        99.1,
        [
            {
                "gap_id": 1,
                "start_time": "2024-03-02 04:00",
                "end_time": "2024-03-03 10:00",
                "duration_text": "1d 6h",
                "missing_candles": 30,
            },
            {
                "gap_id": 2,
                "start_time": "2024-04-11 00:00",
                "end_time": "2024-04-11 12:00",
                "duration_text": "12h",
                "missing_candles": 12,
            },
        ],
        [],
    )
    view.resize(1366, 768)
    return view
