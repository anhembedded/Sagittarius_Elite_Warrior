"""`EPIC-027D` — what the Backtest screen does when its market changes."""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType

from ..ports.i_backtest_screen_state import IBacktestScreenState

logger = logging.getLogger("App.BackTestPresenter")


class MarketSelectionCoordinator:
    """
    @brief Re-points everything market-scoped when the selector changes:
    the symbol picker's catalog, the exchange-rule check, the dirty flag and
    the chart preview.
    @details Candles, catalogs and exchange filters are all per market since
    `EPIC-027A`/`027C`, so a switch that refreshed only some of them would show
    one market's chart next to the other market's symbol list. One handler,
    reached from the ViewModel's `marketChanged`, does all four, in the order
    the screen needs them: the catalog first (so the next picker open lists
    the new market), the rule check next (it reads the cache of the new
    market), then the run config and the preview, which read the market from
    the ViewModel through the config.

    Extension cases, each a local change: clearing a symbol the new market
    does not list (one more step here); a per-market default timeframe (one
    more callable).
    """

    def __init__(
        self,
        state: IBacktestScreenState,
        set_symbol_options_market: Callable[[MarketType], None],
        refresh_market_rule_verification: Callable[[], None],
        notify_config_changed: Callable[[], None],
        request_chart_preview: Callable[[], None],
    ) -> None:
        self._state = state
        self._set_symbol_options_market = set_symbol_options_market
        self._refresh_market_rule_verification = refresh_market_rule_verification
        self._notify_config_changed = notify_config_changed
        self._request_chart_preview = request_chart_preview

    def on_market_changed(self) -> None:
        market = self._state.market
        logger.info("[backtest-config] market set to %s", market.value)
        self._set_symbol_options_market(market)
        self._refresh_market_rule_verification()
        self._notify_config_changed()
        self._request_chart_preview()
