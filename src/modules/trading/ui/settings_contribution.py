"""The factory behind this context's `SETTINGS_SECTION` contribution.

Nothing Qt is imported here at module level — the same rule
`trading/ui/probes.py` follows for its own `DEV_PROBE` factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sagittarius_engine.interfaces.i_container import IContainer

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def build_trading_settings_section(container: IContainer) -> QWidget:
    """The `SETTINGS_SECTION` panel for this module's own config keys."""
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_presenter import (
        TradingSettingsPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_view import (
        TradingSettingsView,
    )

    view = TradingSettingsView()
    # `BasePresenter` holds a reference to its view, never the reverse
    # (`sagittarius_engine.extensions.pyside_mvc.BasePresenter.__init__`), and
    # nothing else here tracks a "presenter" for a contributed widget the way
    # `ScreenRegistry`/`PresenterManager` do for a whole screen. Without this,
    # the Presenter is unreachable the instant this function returns and Qt's
    # signal connections to its bound methods would fire into a dead object.
    view.presenter = TradingSettingsPresenter(view, container)  # type: ignore[attr-defined]
    return view
