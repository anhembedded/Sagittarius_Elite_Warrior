"""`BOT-144` — `DashboardPresenter.__init__`'s construction sequence,
extracted out of the constructor itself.

@details `code/quality.md` §9 gives a "complex multi-step construction
sequence" to a Factory/Builder rather than a constructor body. This one does
not decompose into independent, order-free object constructions the way
`data_management_presenter.py`'s six Coordinators did (see
`coordinator_factory.py`): it interleaves FSM transition wiring, several
closures that read/write `presenter`'s own state, and side-effecting calls
(`_connect_ui_signals()`, `_trigger_initial_health_check()`,
`self._autostart.begin()`) whose relative order is load-bearing. Each of the
four sibling `presenter_factory_*.py` modules (`_core`, `_trading`,
`_indicators`, `_stream`) is therefore a **Builder** over `presenter`, not a
`NamedTuple`-returning Factory: it performs the exact same sequence of
attribute assignments and method calls `__init__` used to perform directly,
just out of line, in the exact original order this function calls them in.
Passing `presenter` itself (rather than its individual fields) mirrors
`coordinator_factory.py`'s own `build_coordinators(presenter, ...)` shape and
is what lets the existing closures over `presenter`'s not-yet-set attributes
(e.g. `get_active_symbol=lambda: presenter._active_symbol`, read long after
`_active_symbol` is finally assigned) keep working unchanged — a closure over
`presenter` behaves identically whether the statement creating it lives
inside `__init__` or in one of these modules.

Originally one function; split into the four sibling modules once this
file itself crossed `architecture-rule.md` §5.4's 400-line ceiling — see
`git log` on this file for that single-function version if a future change
needs the full sequence in one place for reference.

**Real dependency graph (verified against each module's own attribute
reads, not assumed from call order — pull request 273's own review, finding
D14):** `_core`
has no prerequisite; `_trading` and `_indicators` each depend only on
`_core` and are independent of each other (their relative order below is
kept for fidelity to the original constructor, not because either needs the
other's output); `_stream` depends on both `_core` (`_thread_manager`,
`_raw_klines_by_symbol`) and `_indicators` (`_script_runner`), but nothing
`_trading` sets. `_core` must run first and `_stream` must run last; `_trading`
and `_indicators` could swap without breaking either.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .presenter_factory_core import build_core_presenter_state
from .presenter_factory_indicators import build_indicator_presenter_state
from .presenter_factory_stream import build_stream_presenter_state
from .presenter_factory_trading import (
    _ARM_ACTION,
    _EMERGENCY_STOP_ACTION,
    _MANUAL_ORDER_ACTION,
    _TOGGLE_ACTION,
    build_trading_presenter_state,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from ..dashboard_presenter import DashboardPresenter
    from ..dashboard_view import DashboardView

#: Re-exported for `dashboard_presenter.py`'s own later methods
#: (`_on_enable_trading_completed` etc.) — the action-kind strings are
#: defined once, in `presenter_factory_trading.py`, where they are also
#: consumed at construction time.
__all__ = [
    "_ARM_ACTION",
    "_EMERGENCY_STOP_ACTION",
    "_MANUAL_ORDER_ACTION",
    "_TOGGLE_ACTION",
    "build_dashboard_presenter_state",
]


def build_dashboard_presenter_state(
    presenter: DashboardPresenter, view: DashboardView, container: IContainer
) -> None:
    """Performs every construction step `DashboardPresenter.__init__` used to
    perform inline, in the same order, against `presenter` (already past
    `BasePresenter.__init__`, so `presenter.fsm`/`presenter.config`/
    `presenter.view` already exist). Call this exactly once, immediately
    after `super().__init__(view, container)`, and nowhere else."""
    # `BasePresenter.fsm` is typed `BaseStateMachine[Any] | None` (a generic
    # base allows a subclass with no FSM at all); `BasePresenter.__init__`
    # (already run via `super().__init__()` before this function is called)
    # always constructs one for a concrete Presenter, so this narrows a
    # real, always-true invariant rather than guessing around a genuine gap.
    if presenter.fsm is None:
        raise RuntimeError(
            "DashboardPresenter.fsm is None — BasePresenter.__init__ must "
            "run before build_dashboard_presenter_state()."
        )
    fsm = presenter.fsm

    build_core_presenter_state(presenter, view, container, fsm)
    build_trading_presenter_state(presenter, container)
    build_indicator_presenter_state(presenter, container)
    build_stream_presenter_state(presenter, view, container, fsm)
