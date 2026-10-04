"""The factory behind this module's page of Tools → Options (`EPIC-033E`).

Named by a `Deferred` in `module.py`, so `contribute()` imports no widget.
The presenter is the page and holds its view; the shell holds the page.
"""

from __future__ import annotations

from sagittarius_engine.interfaces.i_container import IContainer

from .market_data_settings_presenter import MarketDataSettingsPresenter
from .market_data_settings_view import MarketDataSettingsView


def build_market_data_options_page(
    container: IContainer,
) -> MarketDataSettingsPresenter:
    return MarketDataSettingsPresenter(MarketDataSettingsView(), container)
