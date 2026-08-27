"""The one adapter that knows where the Backtest screen's state actually lives.

@details `EPIC-013C`. `IBacktestScreenState` says *what* the screen holds;
this says *where* — today, on `BackTestPresenter`. Keeping that knowledge in
a single named adapter is the same split `build_coordinators` already makes:
the factory may know the presenter, the coordinators may not.
"""

from __future__ import annotations

from typing import Any

from ..ports.i_backtest_screen_state import IBacktestScreenState


class PresenterBackedScreenState(IBacktestScreenState):
    """
    @brief Reads and writes the Backtest screen's state on the presenter
    that owns it.

    @details **Every member resolves on access — nothing is captured.**
    That is not a style choice: four `EPIC-003E` defects came from binding
    a presenter attribute at construction time while tests replace those
    attributes afterwards, and each was found only because an existing test
    happened to cover it.

    The private-attribute reads below are deliberate and are the reason
    this class exists: they are confined here instead of being spread
    across seventeen lambdas in `coordinators/factory.py`. The presenter
    keeps owning the values because tests read and write several of them
    (`_all_trades`, `_strategy_params`, `_active_preview_id`, ...)
    directly.
    """

    def __init__(self, presenter: Any) -> None:
        self._presenter = presenter

    # -- Read-only --------------------------------------------------- #

    @property
    def symbol(self) -> str:
        return self._presenter._symbol

    @property
    def all_trades(self) -> list[Any]:
        return self._presenter._all_trades

    @property
    def active_strategy_lines(self) -> Any:
        return self._presenter._active_strategy_lines

    @property
    def chart_klines_fetch_limit(self) -> int:
        return self._presenter._chart_klines_fetch_limit

    @property
    def active_preview_id(self) -> int:
        return self._presenter._active_preview_id

    # -- Read/write -------------------------------------------------- #

    @property
    def strategy_params(self) -> dict[str, Any] | None:
        return self._presenter._strategy_params

    @strategy_params.setter
    def strategy_params(self, params: dict[str, Any] | None) -> None:
        self._presenter._set_strategy_params(params)

    @property
    def current_raw_klines(self) -> list[Any]:
        return self._presenter._current_raw_klines

    @current_raw_klines.setter
    def current_raw_klines(self, klines: list[Any]) -> None:
        self._presenter._set_current_raw_klines(klines)

    @property
    def chart_script_keys(self) -> list[str]:
        return self._presenter._chart_script_keys

    @chart_script_keys.setter
    def chart_script_keys(self, keys: list[str]) -> None:
        self._presenter._set_chart_script_keys(keys)
