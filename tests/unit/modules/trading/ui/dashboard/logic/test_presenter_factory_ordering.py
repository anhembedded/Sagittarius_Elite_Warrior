"""PR #273 review finding (Check ID D14, `architecture-rule.md` §7.3) — the
four `presenter_factory_*.py` Builders are documented as "call
first/second/third/last, only from `build_dashboard_presenter_state()`",
but that ordering contract lived only in prose: nothing detected a future
reorder, or a new caller invoking one Builder directly, other than the full
791-test `test_dashboard_presenter.py` suite failing far from the real
cause. These tests make the contract machine-checked: each non-first
Builder reads a `presenter` attribute only an earlier Builder sets, so
calling it before that earlier Builder has run must fail loudly with
`AttributeError`, never construct a silently-broken coordinator.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.logic.presenter_factory_indicators import (
    build_indicator_presenter_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.logic.presenter_factory_stream import (
    build_stream_presenter_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.logic.presenter_factory_trading import (
    build_trading_presenter_state,
)


def _bare_presenter() -> SimpleNamespace:
    """Stands in for `DashboardPresenter` immediately after
    `BasePresenter.__init__()` — before `build_core_presenter_state()` has
    set `_view_model`/`_thread_manager`/etc. Exactly what
    `presenter_factory.py`'s orchestrator passes to the first sub-builder,
    minus everything core hasn't built yet."""
    return SimpleNamespace()


def test_trading_state_requires_core_state_first() -> None:
    """`build_trading_presenter_state()` reads `presenter.view`/
    `presenter._append_log` (and later `_thread_manager`/`_view_model`/
    `_trading_session`), all set only by `build_core_presenter_state()`."""
    with pytest.raises(AttributeError):
        build_trading_presenter_state(_bare_presenter(), container=object())


def test_indicator_state_requires_core_state_first() -> None:
    """`build_indicator_presenter_state()` reads `presenter.config`, set
    only by `BasePresenter.__init__()` plus `presenter._view_model`, set
    only by `build_core_presenter_state()`."""
    with pytest.raises(AttributeError):
        build_indicator_presenter_state(_bare_presenter(), container=object())


def test_stream_state_requires_the_three_earlier_sections_first() -> None:
    """`build_stream_presenter_state()` reads `presenter._thread_manager`/
    `_script_runner`/`_raw_klines_by_symbol`/`_active_interval`, set only by
    the three earlier sections."""
    with pytest.raises(AttributeError):
        build_stream_presenter_state(
            _bare_presenter(), view=object(), container=object(), fsm=object()
        )
