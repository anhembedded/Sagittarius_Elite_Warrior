"""`BOT-112D` — the Data Management screen's Export/Import wiring.

Mirrors `backtesting/ui/test_backtest_presenter.py`'s report-export tests:
`QFileDialog` is patched at the presenter's own import (never invoked for
real), and the background worker itself is exercised directly rather than
through `IThreadManager.submit`, matching every other `_run_*` test in
`test_data_management_presenter.py`.
"""

from __future__ import annotations

import csv
import os
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.export_market_data import (
    ExportMarketDataCommand,
    ExportMarketDataCommandHandler,
    ExportMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.import_market_data import (
    ImportMarketDataCommand,
    ImportMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.export_file_format import (
    ExportFileFormat,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view import (
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PRESENTER_MODULE = (
    "Sagittarius_Elite_Warrior.src.modules.market_data.ui."
    "data_management_presenter.QFileDialog"
)


@pytest.fixture
def export_import_setup(qapp, tmp_path):
    mock_thread_mgr = Mock()
    mock_dispatcher = Mock()
    mock_repo = Mock()
    mock_config = Mock()
    mock_config.get_all.return_value = {}

    def get_config(key, default=None):
        if key == ConfigKeys.MARKET_DATA_EXPORTS_DIR.value:
            return str(tmp_path)
        return default

    mock_config.get.side_effect = get_config

    def resolve_mock(interface):
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IMarketDataRepository:
            return mock_repo
        if interface == IConfig:
            return mock_config
        return Mock()

    container = Mock()
    container.resolve.side_effect = resolve_mock

    view = DataManagementView()
    presenter = DataManagementPresenter(view, container)
    # `__init__` submits `_run_auto_discover` on open — irrelevant to every
    # export/import assertion below, so it is cleared here rather than
    # forcing each test to account for it.
    mock_thread_mgr.submit.reset_mock()
    return presenter, presenter._view_model, mock_thread_mgr, mock_dispatcher, mock_repo


def test_export_requested_opens_dialog_with_selected_symbol_and_format(
    export_import_setup,
):
    _presenter, view_model, mock_thread_mgr, _dispatcher, _repo = export_import_setup
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "15m"
    view_model.selectedExportFormat = "json"

    with patch(f"{_PRESENTER_MODULE}.getSaveFileName", return_value=("", "")) as dlg:
        view_model.requestExport()

    dlg.assert_called_once()
    suggested_path = dlg.call_args[0][2]
    assert suggested_path.endswith(".json")
    assert "BTCUSDT" in suggested_path
    mock_thread_mgr.submit.assert_not_called()


def test_export_cancelled_dialog_does_not_submit_background_work(
    export_import_setup,
):
    _presenter, view_model, mock_thread_mgr, _dispatcher, _repo = export_import_setup

    with patch(f"{_PRESENTER_MODULE}.getSaveFileName", return_value=("", "")):
        view_model.requestExport()

    mock_thread_mgr.submit.assert_not_called()


def test_export_confirmed_path_submits_run_export(export_import_setup, tmp_path):
    presenter, view_model, mock_thread_mgr, _dispatcher, _repo = export_import_setup
    view_model.selectedSymbol = "ETHUSDT"
    view_model.selectedInterval = "1h"
    view_model.selectedExportFormat = "csv"
    dest = str(tmp_path / "chosen.csv")

    with patch(f"{_PRESENTER_MODULE}.getSaveFileName", return_value=(dest, "")):
        view_model.requestExport()

    mock_thread_mgr.submit.assert_called_once_with(
        presenter._run_export, "ETHUSDT", "1h", dest, ExportFileFormat.CSV
    )


def test_run_export_delegates_to_export_import_coordinator(export_import_setup):
    presenter, _view_model, _thread_mgr, mock_dispatcher, _repo = export_import_setup
    mock_dispatcher.dispatch.return_value = ExportMarketDataResult(
        exported_records=1, success=True, message="ok"
    )

    presenter._run_export("BTCUSDT", "1m", "/tmp/x.csv", ExportFileFormat.CSV)

    command = mock_dispatcher.dispatch.call_args[0][1]
    assert isinstance(command, ExportMarketDataCommand)
    assert command.destination_path == "/tmp/x.csv"


def test_import_cancelled_dialog_does_not_submit_background_work(
    export_import_setup,
):
    _presenter, view_model, mock_thread_mgr, _dispatcher, _repo = export_import_setup

    with patch(f"{_PRESENTER_MODULE}.getOpenFileName", return_value=("", "")):
        view_model.requestImport()

    mock_thread_mgr.submit.assert_not_called()


def test_import_confirmed_path_submits_run_import_and_locks_fsm(
    export_import_setup, tmp_path
):
    presenter, view_model, mock_thread_mgr, _dispatcher, _repo = export_import_setup
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "5m"
    source = str(tmp_path / "candles.csv")

    with patch(f"{_PRESENTER_MODULE}.getOpenFileName", return_value=(source, "")):
        view_model.requestImport()

    mock_thread_mgr.submit.assert_called_once_with(
        presenter._run_import, "BTCUSDT", "5m", source
    )
    assert presenter.fsm.current_state == UIMode.CLEARING


def test_run_import_delegates_to_export_import_coordinator(export_import_setup):
    presenter, _view_model, _thread_mgr, mock_dispatcher, _repo = export_import_setup
    mock_dispatcher.dispatch.return_value = ImportMarketDataResult(
        imported_records=3, success=True, message="ok"
    )

    presenter._run_import("BTCUSDT", "1m", "/tmp/in.csv")

    command = mock_dispatcher.dispatch.call_args[0][1]
    assert isinstance(command, ImportMarketDataCommand)
    assert command.source_path == "/tmp/in.csv"


def test_export_dialog_default_directory_falls_back_to_configured_exports_dir(
    export_import_setup, tmp_path
):
    """`resolve_default_exports_dir` must actually create the configured
    directory so the dialog always opens somewhere real, and never leak
    the un-configured `<cwd>/exports` fallback when a directory is set."""
    _presenter, view_model, _thread_mgr, _dispatcher, _repo = export_import_setup
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "1m"
    view_model.selectedExportFormat = "csv"

    with patch(f"{_PRESENTER_MODULE}.getSaveFileName", return_value=("", "")) as dlg:
        view_model.requestExport()

    suggested_path = dlg.call_args[0][2]
    assert suggested_path.startswith(str(tmp_path))
    assert os.path.isdir(tmp_path)


def test_export_format_combo_reflects_view_model_selection(export_import_setup):
    presenter, view_model, _thread_mgr, _dispatcher, _repo = export_import_setup
    view = presenter.view

    view_model.selectedExportFormat = "parquet"

    assert view._cbo_export_format.currentText() == "parquet"


def test_csv_export_writes_real_file_end_to_end(export_import_setup, tmp_path):
    """One end-to-end slice through dispatch → handler → real file, rather
    than stopping at `dispatcher.dispatch` being called (`CS-002`/`CS-003`):
    a wiring test that stubs the dispatcher return value alone would still
    pass if the command never actually reached a real handler."""
    presenter, _view_model, _thread_mgr, _dispatcher, repo = export_import_setup
    handler = ExportMarketDataCommandHandler(repo)
    presenter.dispatcher.dispatch.side_effect = lambda _cmd_type, cmd: handler.execute(
        cmd
    )
    repo.stream_klines.return_value = iter(
        [
            MarketData(
                symbol="BTCUSDT",
                interval=TimeFrame.ONE_MINUTE.value,
                open_time=datetime(2026, 1, 1, tzinfo=UTC),
                open_price=1.0,
                high_price=2.0,
                low_price=0.5,
                close_price=1.5,
                volume=10.0,
                close_time=datetime(2026, 1, 1, 0, 0, 59, tzinfo=UTC),
                quote_asset_volume=1.0,
                number_of_trades=1,
                taker_buy_base_asset_volume=1.0,
                taker_buy_quote_asset_volume=1.0,
            )
        ]
    )
    dest = tmp_path / "real.csv"

    presenter._run_export("BTCUSDT", "1m", str(dest), ExportFileFormat.CSV)

    assert dest.is_file()
    with open(dest, newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTCUSDT"
