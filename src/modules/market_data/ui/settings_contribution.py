"""The factory behind this context's `SETTINGS_SECTION` contribution.

Nothing Qt is imported here at module level, and that is the point — the
same reason `trading/ui/probes.py` gives for its own `DEV_PROBE` factory:
`contribute()` runs at boot for every run, headless `sync` included, and the
widget import must happen only when a surface actually renders it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sagittarius_engine.interfaces.i_container import IContainer

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def build_market_data_settings_section(container: IContainer) -> QWidget:
    """The `SETTINGS_SECTION` panel for this module's own config keys."""
    from Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_settings_presenter import (
        MarketDataSettingsPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_settings_view import (
        MarketDataSettingsView,
    )

    view = MarketDataSettingsView()
    # `BasePresenter` holds a reference to its view, never the reverse
    # (`sagittarius_engine.extensions.pyside_mvc.BasePresenter.__init__`), and
    # nothing else here tracks a "presenter" for a contributed widget the way
    # `ScreenRegistry`/`PresenterManager` do for a whole screen. Without this,
    # the Presenter is unreachable the instant this function returns and Qt's
    # signal connections to its bound methods would fire into a dead object.
    view.presenter = MarketDataSettingsPresenter(view, container)  # type: ignore[attr-defined]
    return view
