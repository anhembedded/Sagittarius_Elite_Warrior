"""The factory behind this module's page of Tools → Options (`EPIC-033E`).

Named by a `Deferred` in `module.py`, so `contribute()` imports no widget.
The presenter is the page and holds its view; the shell holds the page.
"""

from __future__ import annotations

from sagittarius_engine.interfaces.i_container import IContainer

from .trading_settings_presenter import TradingSettingsPresenter
from .trading_settings_view import TradingSettingsView


def build_trading_options_page(container: IContainer) -> TradingSettingsPresenter:
    return TradingSettingsPresenter(TradingSettingsView(), container)
