"""How the Backtest screen tells the user about a failure (`BOT-169`).

Every failure of this screen is one `INotifier` call: a command the user ran
is a modal notice, a background read is an inline bar on the Backtest mode.
The headline is a sentence written in `failure_reporting.py`; the exception
travels as `detail` only. The coordinators' own failures (chart feed, chart
preview, run, sync) are asserted beside their coordinators.
"""

from __future__ import annotations

import os
from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    ReportComparisonDialog,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_screen import (
    BACKTEST_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.failure_reporting import (
    BacktestFailureReporter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestUiState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.symbol_market_metadata_cache import (
    InMemorySymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_chart_overlay_service import (
    StrategyChartOverlayService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from sagittarius_engine.interfaces.i_config import IConfig

from .failure_asserts import assert_command_notice, last_notice

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PRESENTER_MODULE = (
    "Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter"
)
_PICK_FILE = (
    "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
    "logic.report_file_dialogs.QFileDialog.getOpenFileName"
)


@pytest.fixture
def presenter(qapp, notifier, request):
    registry = StrategyRegistry()
    container = Mock()

    def resolve_mock(interface):
        if interface == INotifier:
            return notifier
        if interface == IConfig:
            cfg = Mock()
            cfg.get_all.return_value = {}
            cfg.get.return_value = None
            return cfg
        if interface == StrategyRegistry:
            return registry
        if interface == IStrategyCatalog:
            return StrategyCatalogService(registry)
        if interface == IStrategyChartOverlay:
            return StrategyChartOverlayService(registry)
        if interface == IndicatorScriptRegistry:
            return IndicatorScriptRegistry()
        if interface == BacktestChartHostFactory:
            return BacktestChartHostFactory()
        if interface == ISymbolMarketMetadataCache:
            return InMemorySymbolMarketMetadataCache()
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = BackTestView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    built = BackTestPresenter(view, container)
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return built


# -- the reporter ------------------------------------------------------------


def test_a_command_failure_is_a_modal_notice_with_the_detail_behind_it(notifier):
    BacktestFailureReporter(notifier).run_failed("502 Bad Gateway")

    notice = notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == "backtesting.run"
    assert notice.headline == BacktestFailureReporter.RUN
    assert notice.detail == "502 Bad Gateway"
    assert notice.retry is None


def test_a_background_failure_is_a_bar_on_the_backtest_mode_with_its_retry(notifier):
    def retry() -> None:
        pass

    BacktestFailureReporter(notifier).chart_preview_failed("reset", retry)

    notice = notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert notice.scope == BACKTEST_ROUTE
    assert notice.retry is retry


def test_an_unreadable_file_carries_the_exception_as_detail_only(notifier):
    BacktestFailureReporter(notifier).report_unreadable(OSError("no  such\nfile"))

    notice = notifier.last
    assert notice.cause == "backtesting.report_import"
    assert notice.detail == "no such file"
    assert notice.detail not in notice.headline


def test_every_headline_is_a_sentence_that_names_what_to_do():
    headlines = [
        value
        for name, value in vars(BacktestFailureReporter).items()
        if name.isupper() and isinstance(value, str)
    ]

    assert headlines
    assert all(text.endswith(".") and len(text.split()) >= 6 for text in headlines)


# -- the presenter -----------------------------------------------------------


def test_a_failed_monte_carlo_run_tells_the_user_and_leaves_a_constant_panel_error(
    presenter, notifier
):
    run_id = presenter._claim_monte_carlo_run_id()

    presenter._on_monte_carlo_failed(run_id, "boom")

    assert_command_notice(presenter, "backtesting.monte_carlo", "boom")
    assert (
        presenter._view_model.run_result.monte_carlo_error()
        == BacktestFailureReporter.MONTE_CARLO
    )
    assert len(notifier.failures) == 1


def test_a_stale_monte_carlo_failure_is_ignored(presenter, notifier):
    stale_run_id = presenter._claim_monte_carlo_run_id()
    presenter._claim_monte_carlo_run_id()

    presenter._on_monte_carlo_failed(stale_run_id, "boom")

    assert notifier.failures == []
    assert presenter._view_model.run_result.monte_carlo_error() == ""


def test_a_report_file_that_cannot_be_read_is_a_command_failure(presenter):
    with (
        patch(_PICK_FILE, return_value=("/missing/report.sagi-report.json", "")),
        patch(f"{_PRESENTER_MODULE}.read_backtest_report_bytes") as read,
    ):
        read.side_effect = PermissionError("denied by policy")
        presenter._on_report_import_requested()

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert_command_notice(presenter, "backtesting.report_import", "denied by policy")
    assert last_notice(presenter).headline == BacktestFailureReporter.REPORT_UNREADABLE


def test_a_report_that_fails_to_parse_is_a_command_failure_with_the_loaders_reason(
    presenter, tmp_path
):
    path = tmp_path / "broken.sagi-report.json"
    path.write_bytes(b"not json at all")

    with patch(_PICK_FILE, return_value=(str(path), "")):
        presenter._on_report_import_requested()

    notice = last_notice(presenter)
    assert notice.kind is FailureKind.COMMAND
    assert notice.headline == BacktestFailureReporter.REPORT_INVALID
    assert notice.detail != ""
    assert notice.detail not in notice.headline


def test_a_comparison_report_that_fails_to_load_reaches_the_notifier(
    qapp, presenter, tmp_path
):
    """The dialog knows only the view model; the presenter, wired to its
    signal, is what tells the user."""
    dialog = ReportComparisonDialog(presenter._view_model)
    path = tmp_path / "broken.sagi-report.json"
    path.write_bytes(b"not json at all")

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals."
        "report_comparison_dialog.QFileDialog.getOpenFileName",
        return_value=(str(path), ""),
    ):
        dialog._on_load_column_b()

    notice = last_notice(presenter)
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == "backtesting.report_compare"
    assert notice.headline == BacktestFailureReporter.REPORT_INVALID
    assert notice.detail != ""
    dialog.deleteLater()
