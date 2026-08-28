"""Which pairs the user stars, and which they reached for last.

Deliberately ONE store shared by every screen, not one per screen. A user who
stars `ETHBTC` on Backtest means "this pair matters to me", not "this pair
matters to me on this tab" — a per-screen list would make the same star have
to be set twice, and the two copies would drift.

Persisted through `EPIC-010`'s ui_state, as its own `IStateContributor` under
scope `"symbol_prefs"`. Structural conformance, no base class, matching how
`BackTestPresenter` implements the same protocol.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Protocol

from ...state.state_scope import StateData, StateScope

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

_SCOPE_KEY = "symbol_prefs"
_FAVOURITES_KEY = "favourites"
_RECENTS_KEY = "recents"

#: How many recently chosen pairs to keep. Long enough to cover a session's
#: worth of switching back and forth, short enough that "Gần đây" stays a
#: shortlist rather than a second copy of the full list.
RECENT_LIMIT = 8


def _clean(values: object, limit: int | None = None) -> list[str]:
    """Non-empty upper-case strings from whatever the store handed back.

    Remembered state is read off disk, so it may be any shape at all — a
    corrupted file must degrade to "no favourites yet", never crash the
    screen that reads it (`EPIC-010` boundary rule 4: validation belongs to
    the contributor, not the coordinator).
    """
    if not isinstance(values, (list, tuple)):
        return []
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        symbol = value.strip().upper()
        if symbol and symbol not in cleaned:
            cleaned.append(symbol)
    return cleaned if limit is None else cleaned[:limit]


class _SignalLike(Protocol):
    """Just the half of a Qt signal `bind_picker` uses.

    Structural rather than `SignalInstance`: PySide6's bound signals are not
    a type mypy can name usefully at a call site, and the only thing this
    module needs from one is that it can be connected to.
    """

    def connect(self, slot: object) -> object: ...

    def disconnect(self, slot: object) -> object: ...


class _SymbolPicker(Protocol):
    """What `bind_picker` needs from a picker — `SymbolPickerOverlay` today.

    Named structurally so this module does not import the widget: preferences
    are pure data, and a test double should not have to be a `QDialog`.
    """

    symbol_chosen: _SignalLike
    favourite_toggled: _SignalLike


class SymbolPreferences:
    """@brief The user's starred pairs and their recent choices."""

    def __init__(self, on_changed: Callable[[], None] | None = None) -> None:
        """@param on_changed Called after any mutation, so the owner can mark
        this dirty with the state coordinator. Optional: the store is useful
        (and testable) without persistence wired up."""
        self._favourites: list[str] = []
        self._recents: list[str] = []
        self._on_changed = on_changed

    def set_on_changed(self, on_changed: Callable[[], None]) -> None:
        """Attaches the dirty callback after construction.

        @details The app bootstrapper marks this dirty with the state
        coordinator, and that callback has to name the store — so it cannot
        be passed to `__init__` without a forward reference to the object
        being constructed.
        """
        self._on_changed = on_changed

    # -- Reading -------------------------------------------------------- #

    @property
    def favourites(self) -> Sequence[str]:
        return tuple(self._favourites)

    @property
    def recents(self) -> Sequence[str]:
        return tuple(self._recents)

    def is_favourite(self, symbol: str) -> bool:
        return symbol.strip().upper() in self._favourites

    # -- Writing -------------------------------------------------------- #

    def toggle_favourite(self, symbol: str) -> bool:
        """Stars or unstars `symbol`. Returns its new starred state."""
        key = symbol.strip().upper()
        if not key:
            return False
        if key in self._favourites:
            self._favourites.remove(key)
            starred = False
        else:
            self._favourites.append(key)
            starred = True
        self._notify()
        return starred

    def note_used(self, symbol: str) -> None:
        """Records that `symbol` was just chosen.

        Moves it to the front rather than appending: "Gần đây" ordered by
        first-ever use would freeze after eight pairs and never show the one
        used a minute ago.
        """
        key = symbol.strip().upper()
        if not key:
            return
        if key in self._recents:
            self._recents.remove(key)
        self._recents.insert(0, key)
        del self._recents[RECENT_LIMIT:]
        self._notify()

    def _notify(self) -> None:
        if self._on_changed is not None:
            self._on_changed()

    # -- IStateContributor (structural, no base class) ------------------- #

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key=_SCOPE_KEY)

    def capture_state(self) -> StateData:
        return {
            _FAVOURITES_KEY: list(self._favourites),
            _RECENTS_KEY: list(self._recents),
        }

    def restore_state(self, data: StateData) -> None:
        self._favourites = _clean(data.get(_FAVOURITES_KEY))
        self._recents = _clean(data.get(_RECENTS_KEY), limit=RECENT_LIMIT)

    # -- Convenience for a screen wiring up a picker --------------------- #

    def bind_picker(
        self, picker: _SymbolPicker, on_chosen: Callable[[str], None]
    ) -> None:
        """Wires a `SymbolPickerOverlay` to this store.

        Both screens need exactly these two connections, and getting either
        wrong is silent: a picker with no `favourite_toggled` handler renders
        stars that do nothing, and one that never calls `note_used()` shows a
        permanently empty "Gần đây" tab.
        """
        picker.favourite_toggled.connect(self._on_star_toggled)
        picker.symbol_chosen.connect(self.note_used)
        picker.symbol_chosen.connect(on_chosen)

    def unbind_picker(
        self, picker: _SymbolPicker, on_chosen: Callable[[str], None]
    ) -> None:
        """Undoes `bind_picker`.

        @details Exists because a screen can be handed the shared store
        *after* it has already built its picker against a fallback one
        (`BackTestModalsHost` constructs a private store so a bare host still
        opens a working picker). Rebinding without this would leave both
        stores connected, and every star would be written to a store nothing
        persists as well as to the shared one — invisible until the two
        disagreed.
        """
        picker.favourite_toggled.disconnect(self._on_star_toggled)
        picker.symbol_chosen.disconnect(self.note_used)
        picker.symbol_chosen.disconnect(on_chosen)

    def _on_star_toggled(self, symbol: str) -> None:
        self.toggle_favourite(symbol)

    def seed(self, favourites: Iterable[str] = (), recents: Iterable[str] = ()) -> None:
        """Sets both lists outright — for tests and for a first run that wants
        sensible starting favourites."""
        self._favourites = _clean(favourites)
        self._recents = _clean(recents, limit=RECENT_LIMIT)


def find_symbol_preferences(container: IContainer) -> SymbolPreferences | None:
    """The registered shared store, or `None` when there isn't one.

    @details Same shape, and same reason, as `find_state_coordinator`:
    `PresenterManager` builds every screen as `presenter_class(view,
    container)`, so the container is the only seam, and the same
    `Mock`-returns-a-`Mock` trap applies — a container that cannot say what
    it holds in the shape its own interface promises is treated as holding
    nothing. A screen that gets `None` falls back to its own unshared,
    unpersisted store and still works.
    """
    registrations = container.registrations()
    if not isinstance(registrations, Mapping):
        return None
    if SymbolPreferences not in registrations:
        return None
    resolved = container.resolve(SymbolPreferences)
    return resolved if isinstance(resolved, SymbolPreferences) else None
