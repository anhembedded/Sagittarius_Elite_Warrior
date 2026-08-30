"""`DashboardSymbolPickerSource` — Dashboard's `ISymbolPickerSource` implementer.

@details The one adapter file translating between Dashboard's real data (the
screen ViewModel's `symbolOptions`/`symbol`, the shared `SymbolPreferences` store)
and the standalone picker's app-neutral contract.
Kept apart from `dashboard_symbol_picker_dialog.py` (the `QWidget` composition root
that wires this adapter's VM into a `QDialog`) per `architecture-rule.md` §5: a
Port implementer and the widget wiring that constructs it are different
abstraction levels and do not share a file.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.interfaces.i_symbol_picker_source import (
    ISymbolPickerSource,
)

if TYPE_CHECKING:
    from .dashboard_view_model import DashboardQmlViewModel


class DashboardSymbolPickerSource(ISymbolPickerSource):
    """Reads Dashboard's live symbol data; writes favourite toggles back."""

    def __init__(
        self, view_model: DashboardQmlViewModel, preferences: SymbolPreferences
    ) -> None:
        self._view_model = view_model
        self._preferences = preferences

    def set_preferences(self, preferences: SymbolPreferences) -> None:
        """Swaps the backing store reference."""
        self._preferences = preferences

    def get_symbols(self) -> Sequence[str]:
        return self._view_model.symbolOptions

    def get_favourites(self) -> Sequence[str]:
        return self._preferences.favourites

    def get_recents(self) -> Sequence[str]:
        return self._preferences.recents

    def get_current(self) -> str:
        return self._view_model.symbol

    def set_favourite(self, symbol: str, favourite: bool) -> None:
        if self._preferences.is_favourite(symbol) != favourite:
            self._preferences.toggle_favourite(symbol)
