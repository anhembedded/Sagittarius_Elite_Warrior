"""
Live preview for a single QML screen — no full Sagittarius Engine boot,
no DI container, no mocked dispatcher. Every screen's ViewModel is pure
state with zero I/O (see Docs/Diagrams/ui_architecture.md §3), so it can
be constructed directly and hand-fed a bit of sample data instead of
being wired to a real Presenter.

Usage (from the repo root, with the venv active):
    python Binace_Bot/scripts/preview_qml.py sidebar
    python Binace_Bot/scripts/preview_qml.py settings
    python Binace_Bot/scripts/preview_qml.py database
    python Binace_Bot/scripts/preview_qml.py devboard

Or via the wrapper: scripts/preview-qml.ps1 <screen>

Every screen except Sidebar is a bare QQuickWidget, standing in for what
QmlHostView normally assembles — buttons still emit their request signals
exactly like the real thing, they just have nothing connected on the other
end (no Presenter here), so clicking them is a visual no-op, not a crash.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from Binace_Bot.src.presentation.ui.components.sidebar import Sidebar
from Binace_Bot.src.presentation.ui.components.sidebar.nav_section import (
    NavItem,
    NavSection,
)
from Binace_Bot.src.presentation.ui.screens._qml_shared import (
    create_quick_widget,
)
from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Binace_Bot.src.presentation.ui.screens.data_management.data_management_view_model import (
    DataManagementViewModel,
)
from Binace_Bot.src.presentation.ui.screens.settings.settings_view_model import (
    SettingsViewModel,
)

_SCREENS_DIR = REPO_ROOT / "Binace_Bot" / "src" / "presentation" / "ui" / "screens"

# Same sections MainWindow builds — kept here rather than imported so this
# script never needs to boot main_window.py's other side effects.
_NAV_SECTIONS = [
    NavSection(
        "NAVIGATION",
        (
            NavItem("Dev Board", "dashboard", "layout-dashboard"),
            NavItem("Database", "data_management", "database"),
        ),
    ),
    NavSection(
        "QUANT ENGINE",
        (
            NavItem("Backtest Engine", None, "bar-chart-2", enabled=False),
            NavItem("API & Credentials", "settings", "settings"),
        ),
    ),
]


def _load(quick_widget, qml_dir: Path, filename: str):
    quick_widget.setSource(QUrl.fromLocalFile(str(qml_dir / filename)))
    return quick_widget


def _preview_sidebar():
    sidebar = Sidebar(sections=_NAV_SECTIONS)
    sidebar.set_active("dashboard")
    sidebar.resize(220, 700)
    return sidebar


def _preview_settings():
    quick_widget = create_quick_widget()
    view_model = SettingsViewModel()
    view_model.apiKey = "AbCdEf1234567890GhIjKl"
    view_model.apiSecret = "s3cr3t-do-not-share"
    view_model.defaultSymbols = "BTCUSDT, ETHUSDT"
    view_model.defaultInterval = "1m"
    view_model.defaultSyncDays = 30
    quick_widget.rootContext().setContextProperty("viewModel", view_model)
    quick_widget.resize(760, 520)
    return _load(quick_widget, _SCREENS_DIR / "settings", "SettingsScreen.qml")


def _preview_database():
    quick_widget = create_quick_widget()
    view_model = DataManagementViewModel()
    view_model.status_model.upsert_row(
        "BTCUSDT", "1m", "2024-01-01 00:00", "2024-06-01 00:00", "216,000", "OK"
    )
    view_model.status_model.upsert_row(
        "ETHUSDT",
        "1m",
        "2024-01-01 00:00",
        "2024-05-15 08:00",
        "198,400",
        "3 gaps found!",
    )
    view_model.log_model.append("Checking database status for BTCUSDT (1m)...")
    view_model.log_model.append("Scan complete.", level="success")
    view_model.set_stats("414,400", "128.40 MB")
    quick_widget.rootContext().setContextProperty("viewModel", view_model)
    quick_widget.resize(1400, 820)
    return _load(quick_widget, _SCREENS_DIR / "data_management", "DatabaseScreen.qml")


def _preview_devboard():
    quick_widget = create_quick_widget()
    view_model = DashboardQmlViewModel()
    view_model.set_price_ticker("ETHUSDT  3,241.55", "#26a69a")
    view_model.set_ws_status("WS: LIVE", "#26a69a")
    view_model.log_model.append("Prepared 1 charts.")
    view_model.log_model.append(
        "Live stream for ['ETHUSDT'] is running.", level="success"
    )
    view_model.rsiEnabled = True
    quick_widget.rootContext().setContextProperty("viewModel", view_model)
    quick_widget.resize(420, 760)
    return _load(quick_widget, _SCREENS_DIR / "dashboard", "DevBoardPanel.qml")


_SCREENS = {
    "sidebar": _preview_sidebar,
    "settings": _preview_settings,
    "database": _preview_database,
    "devboard": _preview_devboard,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screen", choices=sorted(_SCREENS))
    args = parser.parse_args()

    app = QApplication(sys.argv)
    widget = _SCREENS[args.screen]()
    widget.setWindowTitle(f"QML Preview — {args.screen}")
    widget.show()

    errors = widget.errors() if hasattr(widget, "errors") else []
    if errors:
        print(f"QML errors: {errors}", file=sys.stderr)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
