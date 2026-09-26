"""`BOT-144` — the Database screen's Coordinator construction (`EPIC-003B`),
extracted out of `DataManagementPresenter.__init__`.

@details Six Coordinators, each wired to the Presenter's own signals and FSM
callbacks, is exactly the "complex multi-step construction sequence" that
`code/quality.md` §9 gives to a Factory rather than leaving inline in a
constructor — the same reasoning that already routes FSM legal-move tables
through `logic/ui_mode_transitions.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)

from ..coordinators import (
    ExportImportCoordinator,
    GapCoordinator,
    KLineInspectorCoordinator,
    ScanCoordinator,
    SyncCoordinator,
    VaultMaintenanceCoordinator,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    from ..data_management_presenter import DataManagementPresenter
    from ..data_management_view_model import DataManagementViewModel


class DataManagementCoordinators(NamedTuple):
    scan: ScanCoordinator
    sync: SyncCoordinator
    gap: GapCoordinator
    kline_inspector: KLineInspectorCoordinator
    export_import: ExportImportCoordinator
    vault_maintenance: VaultMaintenanceCoordinator


def build_coordinators(
    presenter: DataManagementPresenter,
    container: IContainer,
    view_model: DataManagementViewModel,
    thread_manager: IThreadManager,
    market_data_repo: IMarketDataRepository,
) -> DataManagementCoordinators:
    """Constructs every Coordinator this screen owns, wired to `presenter`'s
    own signals, tracker and FSM callbacks. `presenter` must already have its
    `_tracker` in place (read through the `tracker` property) before this is
    called."""
    scan = ScanCoordinator(
        view_model=view_model,
        dispatcher=presenter.dispatcher,
        thread_manager=thread_manager,
        tracker=presenter.tracker,
        market_data_repo=market_data_repo,
        symbol_catalog=container.resolve(ISymbolCatalog),
        ui_log_signal=presenter.ui_log_signal.emit,
        ui_error_log_signal=presenter.ui_error_log_signal.emit,
        ui_status_table_signal=presenter.ui_status_table_signal.emit,
        ui_remove_symbol_signal=presenter.ui_remove_symbol_signal.emit,
        ui_clear_table_signal=presenter.ui_clear_table_signal.emit,
        ui_stats_refresh_signal=presenter.ui_stats_refresh_signal.emit,
        ui_unlock_signal=presenter.ui_unlock_signal.emit,
        ui_symbol_options_signal=presenter.ui_symbol_options_signal.emit,
        ui_known_shard_count_signal=presenter.ui_known_shard_count_signal.emit,
        transition_fsm=presenter._transition_fsm_safe,
        get_current_fsm_state=presenter._get_fsm_state,
        is_shutdown_requested=presenter._is_shutdown,
    )

    sync = SyncCoordinator(
        view_model=view_model,
        dispatcher=presenter.dispatcher,
        market_data_sync=container.resolve(IMarketDataSync),
        thread_manager=thread_manager,
        tracker=presenter.tracker,
        ui_log_signal=presenter.ui_log_signal.emit,
        ui_error_log_signal=presenter.ui_error_log_signal.emit,
        ui_single_sync_progress_signal=presenter.ui_single_sync_progress_signal.emit,
        ui_sync_complete_signal=presenter.ui_sync_complete_signal.emit,
        ui_unlock_signal=presenter.ui_unlock_signal.emit,
        transition_fsm=presenter._transition_fsm_safe,
        get_current_fsm_state=presenter._get_fsm_state,
        is_shutdown_requested=presenter._is_shutdown,
    )

    gap = GapCoordinator(
        dispatcher=presenter.dispatcher,
        thread_manager=thread_manager,
        tracker=presenter.tracker,
        ui_log_signal=presenter.ui_log_signal.emit,
        ui_error_log_signal=presenter.ui_error_log_signal.emit,
        ui_gap_inspector_signal=presenter.ui_gap_inspector_signal.emit,
        ui_unlock_signal=presenter.ui_unlock_signal.emit,
        transition_fsm=presenter._transition_fsm_safe,
        get_current_fsm_state=presenter._get_fsm_state,
        is_shutdown_requested=presenter._is_shutdown,
        on_check_status_callback=scan.run_check_status,
    )

    kline_inspector = KLineInspectorCoordinator(
        dispatcher=presenter.dispatcher,
        historical_klines=container.resolve(IHistoricalKlines),
        thread_manager=thread_manager,
        tracker=presenter.tracker,
        ui_error_log_signal=presenter.ui_error_log_signal.emit,
        ui_kline_inspector_signal=presenter.ui_kline_inspector_signal.emit,
        ui_audit_result_signal=presenter.ui_audit_result_signal.emit,
        get_current_fsm_state=presenter._get_fsm_state,
    )

    export_import = ExportImportCoordinator(
        dispatcher=presenter.dispatcher,
        thread_manager=thread_manager,
        tracker=presenter.tracker,
        ui_log_signal=presenter.ui_log_signal.emit,
        ui_error_log_signal=presenter.ui_error_log_signal.emit,
        ui_unlock_signal=presenter.ui_unlock_signal.emit,
        ui_stats_refresh_signal=presenter.ui_stats_refresh_signal.emit,
        transition_fsm=presenter._transition_fsm_safe,
        get_current_fsm_state=presenter._get_fsm_state,
        is_shutdown_requested=presenter._is_shutdown,
    )

    vault_maintenance = VaultMaintenanceCoordinator(
        dispatcher=presenter.dispatcher,
        thread_manager=thread_manager,
        tracker=presenter.tracker,
        market_data_repo=market_data_repo,
        ui_log_signal=presenter.ui_log_signal.emit,
        ui_error_log_signal=presenter.ui_error_log_signal.emit,
        ui_remove_symbol_signal=presenter.ui_remove_symbol_signal.emit,
        ui_clear_table_signal=presenter.ui_clear_table_signal.emit,
        ui_stats_refresh_signal=presenter.ui_stats_refresh_signal.emit,
        ui_unlock_signal=presenter.ui_unlock_signal.emit,
        transition_fsm=presenter._transition_fsm_safe,
        get_current_fsm_state=presenter._get_fsm_state,
        is_shutdown_requested=presenter._is_shutdown,
    )

    return DataManagementCoordinators(
        scan=scan,
        sync=sync,
        gap=gap,
        kline_inspector=kline_inspector,
        export_import=export_import,
        vault_maintenance=vault_maintenance,
    )
