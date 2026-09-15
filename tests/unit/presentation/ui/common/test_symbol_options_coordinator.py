"""`EPIC-019A` — `SymbolOptionsCoordinator`, extracted out of
`DashboardPresenter` and `BackTestPresenter`.

`EPIC-025` PR 1.2 moved it onto `ISymbolCatalog`, so these tests drive the
port's verified fake instead of a `Mock` dispatcher. Two of them got
stronger for it: "reports ready on a cache miss" now asserts the **symbols**
that reached the picker, where before a mock handed back whatever list the
test itself had written, and the refresh test asserts the flag the module
actually received rather than the shape of a query object.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.symbol_options_coordinator import (
    SymbolOptionsCoordinator,
)


def _thread_manager_runs_inline() -> Mock:
    tm = Mock()
    tm.submit.side_effect = lambda fn, *a, **kw: fn(*a, **kw)
    return tm


def _coordinator(
    catalog: ISymbolCatalog,
    thread_manager: Mock | None = None,
    emit_ready: Mock | None = None,
    emit_failed: Mock | None = None,
) -> SymbolOptionsCoordinator:
    return SymbolOptionsCoordinator(
        symbol_catalog=catalog,
        thread_manager=thread_manager or _thread_manager_runs_inline(),
        emit_ready=emit_ready or Mock(),
        emit_failed=emit_failed or Mock(),
    )


class _ACatalogThatCannotBeRead(ISymbolCatalog):
    """An `ISymbolCatalog` whose read raises, for the failure path.

    A whole implementation rather than a patched method: it inherits the
    port, so the day `ISymbolCatalog` gains a member this class fails to
    instantiate — the reminder `Mock(spec=...)` cannot give.
    """

    def list_symbols(self, *, force_refresh: bool = False) -> tuple[str, ...]:
        raise ConnectionError("exchange unreachable")


def test_request_open_fetches_and_reports_ready_on_cache_miss() -> None:
    emit_ready = Mock()
    emit_failed = Mock()
    coordinator = _coordinator(
        FakeSymbolCatalog(["ETHUSDT", "BTCUSDT"]),
        emit_ready=emit_ready,
        emit_failed=emit_failed,
    )

    coordinator.request_open()

    # The symbols the picker is handed, in the order the port promises —
    # not "a query was dispatched".
    emit_ready.assert_called_once_with(["BTCUSDT", "ETHUSDT"])
    emit_failed.assert_not_called()


def test_request_open_asks_for_the_cached_list_not_a_refresh() -> None:
    """Opening the picker must not force a network round trip: that is what
    the 🔄 button is for (`BUG-066`), and the first open is the common case."""
    catalog = FakeSymbolCatalog(["BTCUSDT"])
    coordinator = _coordinator(catalog)

    coordinator.request_open()

    assert catalog.reads == [False]


def test_request_open_is_a_noop_once_cache_is_populated() -> None:
    catalog = FakeSymbolCatalog(["BTCUSDT"])
    thread_manager = _thread_manager_runs_inline()
    coordinator = _coordinator(catalog, thread_manager=thread_manager)

    coordinator.request_open()
    coordinator.on_options_ready(["BTCUSDT"])
    coordinator.request_open()

    thread_manager.submit.assert_called_once()
    assert catalog.reads == [False], "the second open must not reach the module"


def test_fetch_failure_reports_via_emit_failed_not_emit_ready() -> None:
    emit_ready = Mock()
    emit_failed = Mock()
    coordinator = _coordinator(
        _ACatalogThatCannotBeRead(), emit_ready=emit_ready, emit_failed=emit_failed
    )

    coordinator.request_open()

    emit_ready.assert_not_called()
    emit_failed.assert_called_once_with("exchange unreachable")


def test_request_refresh_bypasses_cache_and_asks_the_module_to_refresh() -> None:
    catalog = FakeSymbolCatalog(["BTCUSDT", "ETHUSDT"])
    emit_ready = Mock()
    coordinator = _coordinator(catalog, emit_ready=emit_ready)
    coordinator.on_options_ready(["BTCUSDT"])

    coordinator.request_refresh()

    assert catalog.was_refreshed() is True
    assert catalog.reads == [True], "a refresh is one read, and it forces one"
    emit_ready.assert_called_once_with(["BTCUSDT", "ETHUSDT"])


def test_on_options_ready_populates_cache_independent_of_fetch() -> None:
    coordinator = _coordinator(FakeSymbolCatalog(), thread_manager=Mock())

    coordinator.on_options_ready(["BTCUSDT"])

    assert coordinator._symbol_options_cache == ["BTCUSDT"]
