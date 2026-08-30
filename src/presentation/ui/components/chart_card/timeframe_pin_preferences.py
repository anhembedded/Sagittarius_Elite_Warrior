"""Which timeframes are pinned to a chart's compact pill row — per symbol,
persisted.

`EPIC-015` Phase 4 shipped `ChartToolbar` with an in-memory-only
`PinnedTimeframes` (`qml/TimeframePicker/timeframe_picker_dialog.py`),
deliberately deferring persistence and cross-card scope — both flagged as
open questions in that phase's module docstring. The user has since decided
both: persist it, and scope it **per chart, keyed by that chart's own
symbol** — not one global set shared by every chart on every screen. A
Backtest screen comparing a 1m scalp symbol against a 1d swing symbol wants
different pins per card, which is exactly the scenario `chart_toolbar.py`'s
docstring named as the reason not to default into a single shared set.

Same structural pattern as `SymbolPreferences`
(`components/symbol_picker/preferences.py`): `IStateContributor`
(structural, no base class), a `set_on_changed` seam the bootstrapper wires
to `state_coordinator.mark_dirty(...)`, and a `find_*` free function reading
the container's registrations so every caller falls back to its own private,
unpersisted instance when running outside full app bootstrap. Deliberately
NOT the same shape otherwise: `SymbolPreferences` holds two flat lists
shared by the whole app; this holds `dict[str, list[str]]` (symbol -> pinned
codes), because "which timeframes I pin" is a genuinely per-chart question,
not a single app-wide preference.

@par Why keyed by symbol, not by which `ChartToolbar` instance exists
Dev Board rebuilds every `ChartCard` (`deleteLater()` + reconstruct) whenever
its symbol list changes (`dashboard_view.py`'s `render_symbol_cards`) — a
`ChartToolbar` Python object is never stable across that rebuild, but the
symbol it was showing is. Keying by symbol is what lets a rebuilt card for
an unchanged symbol recover the same pinned set instead of silently
resetting to the default seed every time a sibling card's symbol changes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

from ...state.state_scope import StateData, StateScope

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

_SCOPE_KEY = "timeframe_pin_prefs"
_PINNED_KEY = "pinned_by_symbol"

#: The pills pinned by default for a symbol never seen before. Five, because
#: the row this seeds lives in a chart header and sixteen would not fit —
#: that constraint is real and stays, but it is only a *starting* pinned set:
#: `TimeframeVM`/`TimeframeToolbar.qml` render whatever this store currently
#: holds for the symbol, and the full picker can pin or unpin any of the
#: domain's sixteen codes from there.
#:
#: Moved here from `chart_toolbar.py` (still re-exported from there for
#: existing call sites/tests) because seeding a never-seen symbol is now this
#: store's own job, not `ChartToolbar`'s constructor default.
DEFAULT_TIMEFRAMES: tuple[str, ...] = ("1m", "5m", "15m", "1h", "1d")


def _normalise_symbol(symbol: str) -> str:
    """Same normalisation `SymbolPreferences` applies: a remembered value or
    a caller passing the raw exchange string must land on the same key."""
    return symbol.strip().upper()


def _clean_codes(values: object) -> list[str] | None:
    """Non-empty, de-duplicated timeframe codes from whatever the store
    handed back for one symbol, or `None` when the shape itself is wrong.

    @details Returning `None` (rather than an empty list) lets the caller
    tell "this symbol's slice was garbage, drop it" apart from "this
    symbol's slice legitimately unpinned everything" — the latter must NOT
    be silently re-seeded with the default on every read.
    """
    if not isinstance(values, (list, tuple)):
        return None
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        code = value.strip()
        if code and code not in cleaned:
            cleaned.append(code)
    return cleaned


class TimeframePinPreferences:
    """@brief Per-symbol pinned-timeframe sets, persisted through `ui_state`.

    @details A screen's composition root does not construct one of these
    itself in production — `app_bootstrapper.py` builds ONE, restores it,
    and registers it as a container singleton, exactly like
    `SymbolPreferences`. `ChartCard`/`ChartToolbar` bind it to their own
    symbol via `bound_to()`, so `TimeframeVM` (which has no concept of
    "which symbol") never has to know this store exists.
    """

    def __init__(self, on_changed: Callable[[], None] | None = None) -> None:
        """@param on_changed Called after any mutation, so the owner can mark
        this dirty with the state coordinator. Optional: the store is useful
        (and testable) without persistence wired up — every `ChartToolbar`
        that gets no store injected falls back to its own private instance
        of this class."""
        self._pinned_by_symbol: dict[str, list[str]] = {}
        self._on_changed = on_changed

    def set_on_changed(self, on_changed: Callable[[], None]) -> None:
        """Attaches the dirty callback after construction — same reason as
        `SymbolPreferences.set_on_changed`: the bootstrapper's callback names
        the store being constructed, so it cannot be passed to `__init__`."""
        self._on_changed = on_changed

    # -- Reading -------------------------------------------------------- #

    def get_pinned(self, symbol: str) -> Sequence[str]:
        """This symbol's pinned codes, seeding `DEFAULT_TIMEFRAMES` the
        first time this symbol is ever asked about — a symbol must never
        show an empty pill row on its first-ever open."""
        key = _normalise_symbol(symbol)
        if key not in self._pinned_by_symbol:
            self._pinned_by_symbol[key] = list(DEFAULT_TIMEFRAMES)
        return tuple(self._pinned_by_symbol[key])

    # -- Writing -------------------------------------------------------- #

    def set_pinned(self, symbol: str, code: str, pinned: bool) -> None:
        """Pins or unpins `code` for `symbol` alone — every other symbol's
        pinned set is untouched, which is the whole point of per-symbol
        scope."""
        key = _normalise_symbol(symbol)
        codes = self._pinned_by_symbol.setdefault(key, list(DEFAULT_TIMEFRAMES))
        if pinned:
            if code not in codes:
                codes.append(code)
        elif code in codes:
            codes.remove(code)
        self._notify()

    def bound_to(
        self, symbol: str
    ) -> tuple[Callable[[], Sequence[str]], Callable[[str, bool], None]]:
        """Partially applies this store to one symbol, matching
        `TimeframeVM`'s `get_pinned`/`set_pinned` callback signatures
        exactly — `TimeframeVM` itself has no concept of "which symbol", so
        the scoping has to happen here, in how the callables are bound, not
        inside the VM."""

        def get_pinned() -> Sequence[str]:
            return self.get_pinned(symbol)

        def set_pinned(code: str, pinned: bool) -> None:
            self.set_pinned(symbol, code, pinned)

        return get_pinned, set_pinned

    def _notify(self) -> None:
        if self._on_changed is not None:
            self._on_changed()

    # -- IStateContributor (structural, no base class) ------------------- #

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key=_SCOPE_KEY)

    def capture_state(self) -> StateData:
        return {
            _PINNED_KEY: {
                symbol: list(codes) for symbol, codes in self._pinned_by_symbol.items()
            }
        }

    def restore_state(self, data: StateData) -> None:
        """Degrades a corrupted slice to "no symbol seen yet" rather than
        raising — `EPIC-010` boundary rule 4: validation belongs to the
        contributor, not the coordinator. A symbol whose own slice is
        malformed is dropped individually rather than discarding every
        other symbol's valid pins."""
        raw = data.get(_PINNED_KEY)
        restored: dict[str, list[str]] = {}
        if isinstance(raw, Mapping):
            for symbol, codes in raw.items():
                if not isinstance(symbol, str):
                    continue
                cleaned = _clean_codes(codes)
                if cleaned is not None:
                    restored[_normalise_symbol(symbol)] = cleaned
        self._pinned_by_symbol = restored


def find_timeframe_pin_preferences(
    container: IContainer,
) -> TimeframePinPreferences | None:
    """The registered shared store, or `None` when there isn't one.

    @details Same shape, and same reason, as `find_symbol_preferences`:
    `PresenterManager` builds every screen as `presenter_class(view,
    container)`, so the container is the only seam, and the same
    `Mock`-returns-a-`Mock` trap applies — a container that cannot say what
    it holds in the shape its own interface promises is treated as holding
    nothing. A caller that gets `None` falls back to its own unshared,
    unpersisted store and still works.
    """
    registrations = container.registrations()
    if not isinstance(registrations, Mapping):
        return None
    if TimeframePinPreferences not in registrations:
        return None
    resolved = container.resolve(TimeframePinPreferences)
    return resolved if isinstance(resolved, TimeframePinPreferences) else None
