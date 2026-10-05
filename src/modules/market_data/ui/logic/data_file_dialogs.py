"""The Data screen's two file dialogs: where to write an export and which CSV
to import.

Moved out of `DataManagementPresenter` (the god-file ratchet, `EPIC-033D`),
the same split as Backtest's `ReportFileDialogs`. Each asks one question
through a native `QFileDialog` parented to the screen's view and returns the
answer, `""` when the person cancelled. They stay off
`ExportImportCoordinator` because a coordinator that opens Qt dialogs cannot
be unit-tested without one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QWidget
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys

from .export_paths import (
    export_file_filter,
    resolve_default_exports_dir,
    suggest_export_filename,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.export_file_format import (
        ExportFileFormat,
    )
    from sagittarius_engine.interfaces.i_config import IConfig


class DataFileDialogs:
    """Asks for a path; `""` means the person cancelled."""

    def __init__(self, parent: QWidget, config: IConfig) -> None:
        self._parent = parent
        self._config = config

    def export_path(
        self, symbol: str, interval: str, file_format: ExportFileFormat
    ) -> str:
        """Where to write the export of `symbol`/`interval`, suggesting a name
        in the configured exports folder."""
        exports_dir = resolve_default_exports_dir(
            self._config.get(ConfigKeys.MARKET_DATA_EXPORTS_DIR.value)
        )
        suggested_name = suggest_export_filename(
            symbol, interval, file_format, datetime.now(UTC)
        )
        path, _selected_filter = QFileDialog.getSaveFileName(
            self._parent,
            "Export Market Data",
            f"{exports_dir}/{suggested_name}",
            export_file_filter(file_format),
        )
        return path

    def import_path(self) -> str:
        """Which CSV to read."""
        path, _selected_filter = QFileDialog.getOpenFileName(
            self._parent, "Import Market Data", "", "CSV Files (*.csv)"
        )
        return path
