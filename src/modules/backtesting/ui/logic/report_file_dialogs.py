"""The Backtest screen's three file dialogs: where to write the trade log's
CSV, where to save a report, and which report to import.

Moved out of `BackTestPresenter` (the god-file ratchet, `EPIC-033D`): each
asks one question of the person through a native `QFileDialog` parented to
the screen's view, and returns the answer, `""` when they cancelled. They stay
off the coordinators for the reason the presenter gave: a coordinator that
opens Qt dialogs cannot be unit-tested without one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QWidget
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys

from .report_export import resolve_default_reports_dir, suggest_report_filename

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_config import IConfig

    from .backtest_run_config import BacktestRunConfig

_EXPORT_DIALOG_TITLE = "Export Trade Logs"
_EXPORT_DEFAULT_FILENAME = "trade_logs.csv"
_EXPORT_FILE_FILTER = "CSV Files (*.csv)"
_REPORT_EXPORT_DIALOG_TITLE = "Save Backtest Report"
_REPORT_EXPORT_FILE_FILTER = (
    "Sagittarius Report (*.sagi-report.json *.sagi-report.json.gz)"
)
_REPORT_IMPORT_DIALOG_TITLE = "Import Backtest Report"


class ReportFileDialogs:
    """Asks for a path; `""` means the person cancelled."""

    def __init__(self, parent: QWidget, config: IConfig) -> None:
        self._parent = parent
        self._config = config

    def trade_log_export_path(self) -> str:
        """Where to write the trade log's CSV."""
        path, _selected_filter = QFileDialog.getSaveFileName(
            self._parent,
            _EXPORT_DIALOG_TITLE,
            _EXPORT_DEFAULT_FILENAME,
            _EXPORT_FILE_FILTER,
        )
        return path

    def report_export_path(self, run_config: BacktestRunConfig) -> str:
        """Where to save the report of `run_config`, suggesting a name built
        from the run's own identity in the configured reports folder."""
        suggested_name = suggest_report_filename(run_config, datetime.now(UTC))
        path, _selected_filter = QFileDialog.getSaveFileName(
            self._parent,
            _REPORT_EXPORT_DIALOG_TITLE,
            f"{self._reports_dir()}/{suggested_name}",
            _REPORT_EXPORT_FILE_FILTER,
        )
        return path

    def report_import_path(self) -> str:
        """Which report to read (`BOT-115C`)."""
        path, _selected_filter = QFileDialog.getOpenFileName(
            self._parent,
            _REPORT_IMPORT_DIALOG_TITLE,
            self._reports_dir(),
            _REPORT_EXPORT_FILE_FILTER,
        )
        return path

    def _reports_dir(self) -> str:
        return resolve_default_reports_dir(
            self._config.get(ConfigKeys.BACKTEST_REPORTS_DIR.value)
        )
