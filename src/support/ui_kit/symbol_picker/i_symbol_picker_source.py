"""Application-neutral data contract for the shared symbol picker.

@par It moved here in `EPIC-025` PR 4.3b
It lived in `presentation/ui/qml/interfaces/`, the one file in that package, and
was written for the QML picker's own view model. The QML picker is deleted (ADR
D21); the **contract** is not, because it is still the right seam: two screens
implement it (`BacktestSymbolPickerSource`, `DashboardSymbolPickerSource`), each
translating its own ViewModel into the four questions a picker asks, and
`architecture-rule.md` §5 is why those adapters do not live in the dialog files
that construct them.

`SymbolPickerOverlay` takes four callables rather than this object, so a caller
with nothing to adapt — Data Management reads its ViewModel directly — passes
lambdas and never sees this file. An implementer's methods are simply the four
callables it is handed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


class ISymbolPickerSource(ABC):
    """What a picker asks its host for, and the one thing it writes back.

    The picker deliberately knows nothing about a screen ViewModel, exchange
    client, persistence store, or application container. A host implements
    this narrow contract and decides where symbols, favourites, recents, and
    the current pair come from.
    """

    @abstractmethod
    def get_symbols(self) -> Sequence[str]:
        """Return the currently available trading pairs."""

    @abstractmethod
    def get_favourites(self) -> Sequence[str]:
        """Return pairs marked as favourites."""

    @abstractmethod
    def get_recents(self) -> Sequence[str]:
        """Return pairs recently selected by the user."""

    @abstractmethod
    def get_current(self) -> str:
        """Return the pair currently selected by the host."""

    @abstractmethod
    def set_favourite(self, symbol: str, favourite: bool) -> None:
        """Persist a favourite toggle raised from the picker.

        Symbols and recents stay host-driven with no picker-side write path;
        favourites is the one piece of state the picker itself can originate
        a change for, so it is the one method on this contract that writes
        back rather than only reading.
        """
