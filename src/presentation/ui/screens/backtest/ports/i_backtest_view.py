"""What `BackTestPresenter` needs of its View — stated, not implied.

@details `EPIC-013B`. Before this file the contract existed only as
scattered attribute access: the presenter, its six coordinators and
`signal_wiring` reached for 14 members of `view` with no type anywhere
saying they exist. That is the *implicit* duck typing
`architecture-rule.md` §2.1 forbids — the declared contract and the real
one had drifted apart with nothing to notice, which is precisely what
happened to the engine's `IView` (it declares one method, `bind()`, that
no View in either repo implements).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ....components.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
from ....components.symbol_picker import SymbolPreferences
from ..backtest_view_model import BackTestViewModel
from ..logic.chart_canvas_view import ChartDisplayMode
from .i_backtest_chart_controls import IBacktestChartControls
from .i_backtest_chart_host import IBacktestChartHost
from .i_backtest_chart_host_factory import IBacktestChartHostFactory

#: `set_view_model`'s second argument, a QML-era leftover kept because
#: `BaseView.set_view_model` still accepts it. Named rather than repeated as
#: a literal default, per `code-quality-rule.md` "No Magic Numbers".
DEFAULT_VIEW_MODEL_CONTEXT_NAME = "viewModel"


@runtime_checkable
class IBacktestView(Protocol):
    """
    @brief The Backtest screen's Presenter↔View contract — all 17 members
    the Presenter side actually uses, and nothing else.

    @details **`Protocol`, not an ABC**, under `architecture-rule.md` §2.1
    reasons **(a)** and **(b)**: every implementer is a `QWidget` subclass
    (via `BaseView`), where `ABCMeta` collides with Shiboken's metaclass,
    and where a second base would break §2's "NO Multiple Inheritance".
    The same constraint `ui/kit/style.py` documents for `apply_role()`.

    **Deliberately not derived from the engine's `IView`.** `IView`
    declares `bind()`, which no View in either repo implements and which
    this app references nowhere; inheriting it would force every Backtest
    View to grow a method solely to satisfy an unused interface. Whether
    `IView` should be redefined or dropped is the engine repo's call —
    see `EPIC-013B`.

    **What is NOT here, on purpose:** `resize()`. It is called once, by
    `preview.py`, a standalone developer harness that constructs a
    `BackTestView()` directly — not across the Presenter↔View boundary
    this port describes. Widening the port to cover a harness would make
    every future View owe a method the Presenter never calls, which is the
    Interface Segregation violation §1 (I) warns about.

    **Enforcement:** `presentation/` is excluded from the `mypy` gate
    wholesale (`pyproject.toml`, `EPIC-002A` — PySide6 `@Property`
    false positives), so type checking alone does NOT police this port.
    `tests/unit/presentation/ui/screens/backtest/test_backtest_view_contract.py`
    is the mechanism that does: it walks the Presenter-side modules with
    `ast` and fails when the members they touch and the members declared
    here stop matching, in either direction.
    """

    # -- Attributes -------------------------------------------------- #

    #: Chart hosts currently mounted, in render order. A *list*, not a
    #: cached single card: `BUG-013` showed a cached card becoming a
    #: `deleteLater()`-ed C++ object after a host rebuild, so callers must
    #: re-read this every time rather than hold on to an element.
    chart_cards: list[IBacktestChartHost]

    #: The chart toolbar, or `None` before `render_symbol_cards()` has
    #: built it. The `None` is load-bearing — `signal_wiring` connects to
    #: it only after cards exist.
    chart_controls: IBacktestChartControls | None

    #: Which of price / equity / both the chart is currently showing. Read
    #: by `IndicatorCoordinator` to decide whether price-scale overlays
    #: mean anything. Reached through `getattr(view, "chart_mode",
    #: ChartDisplayMode.OHLC)` until `EPIC-013C` — a capability probe by
    #: string, which is the `hasattr`/`getattr` form §2.1 forbids and which
    #: no AST walk over attribute access can see. Declared here so it is a
    #: contract rather than a guess; the fallback default is gone with it.
    chart_mode: ChartDisplayMode

    # -- Lifecycle --------------------------------------------------- #

    def set_view_model(
        self,
        view_model: BackTestViewModel,
        context_name: str = DEFAULT_VIEW_MODEL_CONTEXT_NAME,
    ) -> None:
        """Registers the ViewModel and builds every child that needs it."""
        ...

    def render_symbol_cards(self, symbols: list[str]) -> list[IBacktestChartHost]:
        """(Re)builds one chart host per symbol and returns them."""
        ...

    def set_symbol_preferences(self, preferences: SymbolPreferences) -> None:
        """Injects the container-registered symbol favourites/recents store.

        @details `EPIC-014`. Same shape and the same reason as
        `set_chart_host_factory` below: the View self-constructs an
        unpersisted default so a bare `BackTestView()` works, and the
        Presenter — which has the container — replaces it with the shared
        one.
        """
        ...

    def set_timeframe_pin_preferences(
        self, preferences: TimeframePinPreferences
    ) -> None:
        """Injects the container-registered, per-symbol pinned-timeframe
        store.

        @details Follow-up to `EPIC-015` Phase 4. Same shape as
        `set_symbol_preferences` just above: the View self-constructs an
        unpersisted default so a bare `BackTestView()` works, and the
        Presenter replaces it with the shared, persisted one before the
        first `render_symbol_cards()` call — every chart host built from
        then on is scoped to its own symbol against this one store.
        """
        ...

    # -- Chart host configuration ------------------------------------ #

    def set_chart_host_factory(self, factory: IBacktestChartHostFactory) -> None:
        """Overrides the View's self-constructed default with the DI one."""
        ...

    def set_chart_mode(self, mode: ChartDisplayMode) -> None: ...

    def set_chart_dev_mode(self, enabled: bool) -> None: ...

    def set_chart_opengl_enabled(self, enabled: bool) -> None: ...

    def set_chart_cached_interaction_enabled(self, enabled: bool) -> None: ...

    # -- Display toggles --------------------------------------------- #

    def set_display_timezone(self, tz_name: str) -> None: ...

    def set_volume_visible(self, visible: bool) -> None: ...

    def set_trade_flags_visible(self, visible: bool) -> None: ...

    # -- Data arriving ----------------------------------------------- #

    def on_preview_data_ready(self, klines: list, volume: list) -> None:
        """Local candles for a newly selected range, before any run exists."""
        ...

    def on_backtest_data_ready(
        self, result: object, klines: list, volume: list
    ) -> None:
        """A finished run's candles, volume and trades."""
        ...
