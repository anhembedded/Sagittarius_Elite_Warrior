"""`EPIC-019A` — `SymbolOptionsCoordinator`, extracted out of
`DashboardPresenter` and `BackTestPresenter`."""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols import (
    ListAvailableSymbolsQuery,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.symbol_options_coordinator import (
    SymbolOptionsCoordinator,
)


def _thread_manager_runs_inline() -> Mock:
    tm = Mock()
    tm.submit.side_effect = lambda fn, *a, **kw: fn(*a, **kw)
    return tm


def test_request_open_fetches_and_reports_ready_on_cache_miss() -> None:
    dispatcher = Mock()
    dispatcher.dispatch.return_value = ["BTCUSDT", "ETHUSDT"]
    emit_ready = Mock()
    emit_failed = Mock()
    coordinator = SymbolOptionsCoordinator(
        dispatcher=dispatcher,
        thread_manager=_thread_manager_runs_inline(),
        emit_ready=emit_ready,
        emit_failed=emit_failed,
    )

    coordinator.request_open()

    dispatcher.dispatch.assert_called_once_with(
        ListAvailableSymbolsQuery, ListAvailableSymbolsQuery()
    )
    emit_ready.assert_called_once_with(["BTCUSDT", "ETHUSDT"])
    emit_failed.assert_not_called()


def test_request_open_is_a_noop_once_cache_is_populated() -> None:
    dispatcher = Mock()
    dispatcher.dispatch.return_value = ["BTCUSDT"]
    thread_manager = _thread_manager_runs_inline()
    coordinator = SymbolOptionsCoordinator(
        dispatcher=dispatcher,
        thread_manager=thread_manager,
        emit_ready=Mock(),
        emit_failed=Mock(),
    )

    coordinator.request_open()
    coordinator.on_options_ready(["BTCUSDT"])
    coordinator.request_open()

    thread_manager.submit.assert_called_once()


def test_fetch_failure_reports_via_emit_failed_not_emit_ready() -> None:
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = ConnectionError("exchange unreachable")
    emit_ready = Mock()
    emit_failed = Mock()
    coordinator = SymbolOptionsCoordinator(
        dispatcher=dispatcher,
        thread_manager=_thread_manager_runs_inline(),
        emit_ready=emit_ready,
        emit_failed=emit_failed,
    )

    coordinator.request_open()

    emit_ready.assert_not_called()
    emit_failed.assert_called_once_with("exchange unreachable")


def test_request_refresh_bypasses_cache_and_forces_force_refresh_query() -> None:
    dispatcher = Mock()
    dispatcher.dispatch.return_value = ["BTCUSDT", "ETHUSDT"]
    thread_manager = _thread_manager_runs_inline()
    emit_ready = Mock()
    coordinator = SymbolOptionsCoordinator(
        dispatcher=dispatcher,
        thread_manager=thread_manager,
        emit_ready=emit_ready,
        emit_failed=Mock(),
    )
    coordinator.on_options_ready(["BTCUSDT"])

    coordinator.request_refresh()

    dispatcher.dispatch.assert_called_once_with(
        ListAvailableSymbolsQuery, ListAvailableSymbolsQuery(force_refresh=True)
    )
    emit_ready.assert_called_once_with(["BTCUSDT", "ETHUSDT"])


def test_on_options_ready_populates_cache_independent_of_fetch() -> None:
    coordinator = SymbolOptionsCoordinator(
        dispatcher=Mock(),
        thread_manager=Mock(),
        emit_ready=Mock(),
        emit_failed=Mock(),
    )

    coordinator.on_options_ready(["BTCUSDT"])

    assert coordinator._symbol_options_cache == ["BTCUSDT"]
