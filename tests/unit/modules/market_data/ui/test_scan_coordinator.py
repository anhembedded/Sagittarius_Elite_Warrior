from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.prune_empty_shards import (
    PruneEmptyShardsCommand,
    PruneEmptyShardsResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.scan_all_databases import (
    DatabaseStatusDTO,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.coordinators import (
    DataManagementActionKind,
    ScanCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_signal_payloads import (
    StatusRowUpdate,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode


@pytest.fixture
def scan_fixture():
    view_model = Mock()
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "15m"
    view_model.symbols = ["BTCUSDT"]
    view_model.intervals = ["15m"]

    dispatcher = Mock()
    thread_manager = Mock()
    tracker = ActionOwnershipTracker[DataManagementActionKind, object, UIMode]()
    market_data_repo = Mock()
    market_data_repo.list_available_shards.return_value = []

    signals = {
        "ui_log": Mock(),
        "ui_error_log": Mock(),
        "ui_status_table": Mock(),
        "ui_remove_symbol": Mock(),
        "ui_clear_table": Mock(),
        "ui_stats_refresh": Mock(),
        "ui_unlock": Mock(),
        "ui_symbol_options": Mock(),
        "ui_known_shard_count": Mock(),
        "transition_fsm": Mock(return_value=True),
        "get_fsm_state": Mock(return_value=UIMode.IDLE),
        "is_shutdown_requested": Mock(return_value=False),
    }

    symbol_catalog = FakeSymbolCatalog()

    coordinator = ScanCoordinator(
        view_model=view_model,
        dispatcher=dispatcher,
        thread_manager=thread_manager,
        tracker=tracker,
        market_data_repo=market_data_repo,
        symbol_catalog=symbol_catalog,
        ui_log_signal=signals["ui_log"],
        ui_error_log_signal=signals["ui_error_log"],
        ui_status_table_signal=signals["ui_status_table"],
        ui_remove_symbol_signal=signals["ui_remove_symbol"],
        ui_clear_table_signal=signals["ui_clear_table"],
        ui_stats_refresh_signal=signals["ui_stats_refresh"],
        ui_unlock_signal=signals["ui_unlock"],
        ui_symbol_options_signal=signals["ui_symbol_options"],
        ui_known_shard_count_signal=signals["ui_known_shard_count"],
        transition_fsm=signals["transition_fsm"],
        get_current_fsm_state=signals["get_fsm_state"],
        is_shutdown_requested=signals["is_shutdown_requested"],
    )

    return coordinator, dispatcher, market_data_repo, tracker, signals, symbol_catalog


def test_scan_coordinator_auto_discover_never_opens_a_shard_session(scan_fixture):
    """BOT-120 — screen-open auto-discover must stay a directory listing: one
    cached `ISymbolCatalog` read plus a call to `list_available_shards()`. It
    must never dispatch ScanAllDatabasesQuery or PruneEmptyShardsCommand —
    those open one SQLite session per shard and are now explicit-action-only
    (see run_scan_all).

    `EPIC-025` PR 1.2 — the symbol read is a port, so "cheap" is now
    assertable rather than implied: `catalog.reads == [False]` says the read
    did not force an exchange round trip, which no dispatch assertion could
    tell you."""
    coordinator, dispatcher, market_data_repo, tracker, signals, catalog = scan_fixture

    catalog.seed(["BTCUSDT", "ETHUSDT"])
    market_data_repo.list_available_shards.return_value = ["BTCUSDT"]

    coordinator.run_auto_discover()

    assert catalog.reads == [False], "auto-discover reads the cache, not the exchange"
    dispatcher.dispatch.assert_not_called()
    market_data_repo.list_available_shards.assert_called_once()
    signals["ui_symbol_options"].assert_called_once_with(["BTCUSDT", "ETHUSDT"])
    signals["ui_status_table"].assert_not_called()
    assert any(
        "1 local data file" in str(call.args[0])
        for call in signals["ui_log"].call_args_list
    )
    # Regression: the empty-state placeholder cannot tell "genuinely empty
    # vault" apart from "vault has data, not scanned yet" from rowCount alone
    # (both are 0) — it needs this count reported separately, every time.
    signals["ui_known_shard_count"].assert_called_once_with(1)
    signals["ui_stats_refresh"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_auto_discover_reports_an_empty_vault_truthfully(
    scan_fixture,
):
    coordinator, _dispatcher, market_data_repo, tracker, signals, _catalog = (
        scan_fixture
    )

    # An empty catalog: the exchange list is unavailable or has nothing.
    market_data_repo.list_available_shards.return_value = []

    coordinator.run_auto_discover()

    signals["ui_symbol_options"].assert_not_called()
    assert any(
        "is empty" in str(call.args[0]) for call in signals["ui_log"].call_args_list
    )
    signals["ui_known_shard_count"].assert_called_once_with(0)
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_scan_all_populates_table(scan_fixture):
    coordinator, dispatcher, _, tracker, signals, _catalog = scan_fixture

    status_dto = DatabaseStatusDTO(
        symbol="BTCUSDT",
        interval="15m",
        first_record="2024-01-01",
        last_record="2024-01-02",
        total_candles="100",
        gaps="0",
        status_text="OK",
    )
    dispatcher.dispatch.side_effect = [
        [status_dto],  # ScanAllDatabasesQuery
        PruneEmptyShardsResult(removed_symbols=[], scanned_count=0),  # BUG-078
    ]

    coordinator.run_scan_all(["BTCUSDT"], ["15m"])

    # EPIC-008G §3: signal mang `StatusRowUpdate` thay vì 6 chuỗi vị trí, nên
    # assert theo TÊN trường — hoán nhầm 2 cột giờ làm test đỏ chứ không lọt.
    signals["ui_status_table"].assert_called_once_with(
        StatusRowUpdate(
            symbol="BTCUSDT",
            first_record="2024-01-01",
            last_record="2024-01-02",
            total_candles="100",
            status_text="OK",
            interval="15m",
        )
    )
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_scan_all_dispatches_prune_and_reports_removals(
    scan_fixture,
):
    """BUG-078 / BOT-120 — the explicit full scan must dispatch
    PruneEmptyShardsCommand as its last step and surface a log line when it
    actually removed something. This used to be auto-discover's job; it moved
    here so opening every shard's session is always an explicit user action."""
    coordinator, dispatcher, _, tracker, signals, _catalog = scan_fixture

    dispatcher.dispatch.side_effect = [
        [],  # ScanAllDatabasesQuery
        PruneEmptyShardsResult(
            removed_symbols=["PHANTOM1", "PHANTOM2"], scanned_count=5
        ),
    ]

    coordinator.run_scan_all([], ["1m"])

    assert dispatcher.dispatch.call_count == 2
    prune_call = dispatcher.dispatch.call_args_list[1]
    assert prune_call.args[0] is PruneEmptyShardsCommand
    assert any(
        "2 empty shard" in str(call.args[0])
        for call in signals["ui_log"].call_args_list
    )
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_scan_all_refreshes_known_shard_count_after_prune(
    scan_fixture,
):
    """Regression: a scan that finds nothing and prunes every stray shard it
    turned up must not leave the empty-state placeholder still quoting a
    stale pre-prune count — refresh it from a fresh listing afterwards."""
    coordinator, dispatcher, market_data_repo, _tracker, signals, _catalog = (
        scan_fixture
    )
    market_data_repo.list_available_shards.return_value = []  # post-prune

    dispatcher.dispatch.side_effect = [
        [],  # ScanAllDatabasesQuery
        PruneEmptyShardsResult(removed_symbols=["PHANTOM1"], scanned_count=1),
    ]

    coordinator.run_scan_all([], ["1m"])

    signals["ui_known_shard_count"].assert_called_once_with(0)


def test_scan_coordinator_scan_all_survives_prune_failure(scan_fixture):
    """A broken prune pass must not fail the whole scan-all action — it's a
    hygiene pass, not the reason the user clicked Scan All."""
    coordinator, dispatcher, _, tracker, _signals, _catalog = scan_fixture

    dispatcher.dispatch.side_effect = [
        [],  # ScanAllDatabasesQuery
        Exception("disk unavailable"),  # PruneEmptyShardsCommand
    ]

    coordinator.run_scan_all([], ["1m"])

    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_check_status_success(scan_fixture):
    coordinator, dispatcher, _, tracker, signals, _catalog = scan_fixture

    status_dto = DatabaseStatusDTO(
        symbol="BTCUSDT",
        interval="15m",
        first_record="2024-01-01",
        last_record="2024-01-02",
        total_candles="500",
        gaps="0",
        status_text="OK",
    )
    dispatcher.dispatch.return_value = status_dto

    coordinator.run_check_status("BTCUSDT", "15m")

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], GetDatabaseStatusQuery)
    # EPIC-008G §3: signal mang `StatusRowUpdate` thay vì 6 chuỗi vị trí, nên
    # assert theo TÊN trường — hoán nhầm 2 cột giờ làm test đỏ chứ không lọt.
    signals["ui_status_table"].assert_called_once_with(
        StatusRowUpdate(
            symbol="BTCUSDT",
            first_record="2024-01-01",
            last_record="2024-01-02",
            total_candles="500",
            status_text="OK",
            interval="15m",
        )
    )
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_cancel_is_wired_into_scan_query(scan_fixture):
    """BUG-041: coordinator cancellation must reach the application handler."""
    coordinator, dispatcher, _, _, _, _ = scan_fixture
    dispatcher.dispatch.return_value = []

    cancellation_token = coordinator.create_cancellation_token()
    coordinator.cancel()
    coordinator.run_scan_all(["BTCUSDT"], ["1m"], cancellation_token)

    query = dispatcher.dispatch.call_args.args[1]
    assert query.cancellation_requested is not None
    assert query.cancellation_requested() is True


# ---------------------------------------------------------------------------
# `request_*` orchestration (BOT-144) — validate/log/transition/submit, moved
# here from the Presenter's own Slots. `run_*` above is unaffected: these
# methods only decide whether and how to submit it.
# ---------------------------------------------------------------------------


def test_request_check_status_transitions_and_submits_with_the_given_selection(
    scan_fixture,
):
    coordinator, _dispatcher, _repo, _tracker, signals, _catalog = scan_fixture
    thread_manager = coordinator._thread_manager

    coordinator.request_check_status("BTCUSDT", "1h")

    signals["transition_fsm"].assert_called_once_with(UIMode.SCANNING)
    thread_manager.submit.assert_called_once_with(
        coordinator.run_check_status, "BTCUSDT", "1h"
    )


def test_request_check_all_status_clears_table_and_submits_empty_symbol_list(
    scan_fixture,
):
    """BOT-120: the empty symbol list is what makes the handler fall back to
    on-disk shards instead of the full exchange catalogue."""
    coordinator, _dispatcher, _repo, _tracker, signals, _catalog = scan_fixture
    thread_manager = coordinator._thread_manager

    coordinator.request_check_all_status(["1m", "15m"])

    signals["ui_clear_table"].assert_called_once()
    signals["transition_fsm"].assert_called_once_with(UIMode.SCANNING)
    method, symbols, intervals, token = thread_manager.submit.call_args.args
    assert method == coordinator.run_scan_all
    assert symbols == []
    assert intervals == ["1m", "15m"]
    assert token is not None


def test_request_check_all_status_does_nothing_once_shutdown(scan_fixture):
    coordinator, _dispatcher, _repo, _tracker, signals, _catalog = scan_fixture
    signals["is_shutdown_requested"].return_value = True

    coordinator.request_check_all_status(["1m"])

    signals["transition_fsm"].assert_not_called()
    coordinator._thread_manager.submit.assert_not_called()


#: Clear/purge/VACUUM's own `request_*` tests moved to
#: `test_vault_maintenance_coordinator.py` alongside their `run_*` tests
#: (BOT-144, `VaultMaintenanceCoordinator` extraction).
