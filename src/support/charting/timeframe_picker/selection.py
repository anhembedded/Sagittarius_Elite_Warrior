"""The timeframe a chart is on, the set pinned beside it, and what is offered.

## One state object, two views — and that is why it survived the QML

`EPIC-015` wrote this as `TimeframeVM`, a `QObject` publishing everything as
Qt properties for `TimeframeToolbar.qml` (the compact pill row) and
`TimeframePicker.qml` (the full grouped grid) to bind to. The user's own
instruction shaped it: *"2 widget, common nếu reuse được"* — pinning a timeframe
in one view has to show in the other at once, so the two views share one state
object rather than each holding a copy.

`EPIC-025` PR 4.3k deletes both `.qml` files (ADR D21) and keeps exactly that:
one `QObject` two widgets read, with its property and slot decorations dropped
because nothing binds to it any more. What is left is a small model — plain
Python properties, two signals, and the four calls a view makes — and it is the
reason a `QPushButton` row and a `QTreeWidget` dialog cannot drift apart.

Reads `catalogue.py` for the domain-derived grouping and labels rather than
re-deriving them: that module takes no Qt import precisely so something else can
read it, and a timeframe added to the domain's `TimeFrame` enum lands in both
views with no second edit.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from .catalogue import (
    GROUP_CAPTIONS,
    GROUP_LABELS,
    TimeframeOption,
    group_options,
    options_for,
)


@dataclass(frozen=True)
class PinnedTimeframe:
    """One pill in the compact row: its code, and whether it is the current
    one."""

    code: str
    current: bool


@dataclass(frozen=True)
class TimeframeChoice:
    """One cell in the full grid."""

    code: str
    label: str
    pinned: bool
    current: bool


@dataclass(frozen=True)
class CurrentStaysPinned:
    """A host's rule that the timeframe chosen stays pinned, so the row always shows it
    (`EPIC-040` F4: the backtest workbench's interval row shows the interval Run replays).
    Choosing a timeframe pins it, and the one chosen cannot be unpinned; `reason` is what a person
    who tries is told."""

    reason: str


@dataclass(frozen=True)
class TimeframeGroupView:
    """One titled group of the grid — the catalogue's own grouping, with its
    caption."""

    label: str
    caption: str
    rows: tuple[TimeframeChoice, ...]


class TimeframeSelection(QObject):
    """
    @brief The catalogue narrowed to what a screen offers, with a pinned subset
    and one current code. Read by both views this widget has.

    @details Callback-constructed, not handed a screen ViewModel: this widget
    has no opinion about which screen owns it. `set_pinned` is a write-through
    call rather than a signal the host might ignore — the same symmetric
    read/write shape `ISymbolPickerSource.set_favourite` has.
    """

    #: Anything a view renders has changed; both views re-read everything.
    stateChanged = Signal()
    #: A code the **user** picked. `set_current()` deliberately does not emit
    #: it — see that method.
    chosen = Signal(str)
    #: The person tried to unpin the chosen timeframe under `CurrentStaysPinned`; carries its reason. The views have already
    #: been told to re-read, so a box they cleared is checked again.
    pin_refused = Signal(str)

    def __init__(
        self,
        *,
        get_codes: Callable[[], Sequence[str]],
        get_current: Callable[[], str],
        get_pinned: Callable[[], Sequence[str]],
        set_pinned: Callable[[str, bool], None],
        keep_current_pinned: CurrentStaysPinned | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._keep_current_pinned = keep_current_pinned
        self._get_codes = get_codes
        self._get_current = get_current
        self._get_pinned = get_pinned
        self._set_pinned = set_pinned

        self._options: list[TimeframeOption] = []
        self._current = ""
        self._pinned: set[str] = set()
        self._pinned_rows: tuple[PinnedTimeframe, ...] = ()
        self._groups: tuple[TimeframeGroupView, ...] = ()
        self._has_warning = False

    # -- reading -----------------------------------------------------------

    @property
    def pinned_rows(self) -> tuple[PinnedTimeframe, ...]:
        """The pinned codes in catalogue (duration) order — the pill row reads
        only this."""
        return self._pinned_rows

    @property
    def groups(self) -> tuple[TimeframeGroupView, ...]:
        """One entry per non-empty group — the full grid reads only this."""
        return self._groups

    @property
    def current_code(self) -> str:
        return self._current

    @property
    def has_warning(self) -> bool:
        """Whether any offered option is sub-minute, which the grid warns
        about: one day of 1s candles is about 86,400 of them."""
        return self._has_warning

    # -- writing -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-reads codes, current and pinned from the host, then rebuilds both
        views. Public because a screen's option list changes at runtime."""
        self._options = options_for(list(self._get_codes()))
        self._current = self._get_current()
        self._pinned = {str(code) for code in self._get_pinned()}
        self._pin_the_current()
        self._recompute()

    def set_current(self, code: str | None) -> None:
        """Sets the active code **without** emitting `chosen`.

        @details For a caller that already knows the new interval because it
        fired elsewhere and only needs the highlight to catch up —
        `ChartToolbar.set_active()`'s contract, kept from the QtWidgets original
        through the QML era and back. `choose()` cannot be reused: it always
        emits, which would feed straight back into the handler that called this.

        Unlike `choose()`, it does not require membership in the offered codes:
        a stale config entry still updates `current_code` faithfully rather than
        being silently dropped. It simply highlights nothing.
        """
        self._current = code or ""
        self._pin_the_current()
        self._recompute()

    def choose(self, code: str) -> None:
        """The user picked a code. Ignored unless it is actually offered."""
        if not any(option.code == code for option in self._options):
            return
        self._current = code
        self._pin_the_current()
        self._recompute()
        self.chosen.emit(code)

    def toggle_pinned(self, code: str) -> None:
        """Pins or unpins a code, writing through to the host that owns the
        set. Ignored unless the code is actually offered."""
        if not any(option.code == code for option in self._options):
            return
        pin = code not in self._pinned
        rule = self._keep_current_pinned
        if not pin and rule is not None and code == self._current:
            self._recompute()
            self.pin_refused.emit(rule.reason)
            return
        if pin:
            self._pinned.add(code)
        else:
            self._pinned.discard(code)
        self._set_pinned(code, pin)
        self._recompute()

    # -- internal ----------------------------------------------------------

    def _pin_the_current(self) -> None:
        """Under `CurrentStaysPinned` the timeframe chosen is pinned: written through to the host
        when it is offered and not yet pinned."""
        current = self._current
        offered = any(option.code == current for option in self._options)
        if (
            self._keep_current_pinned is not None
            and offered
            and current not in self._pinned
        ):
            self._pinned.add(current)
            self._set_pinned(current, True)

    def _recompute(self) -> None:
        self._pinned_rows = tuple(
            PinnedTimeframe(code=option.code, current=option.code == self._current)
            for option in self._options
            if option.code in self._pinned
        )
        self._groups = tuple(
            TimeframeGroupView(
                label=GROUP_LABELS[group],
                caption=GROUP_CAPTIONS[group],
                rows=tuple(
                    TimeframeChoice(
                        code=option.code,
                        label=option.label,
                        pinned=option.code in self._pinned,
                        current=option.code == self._current,
                    )
                    for option in members
                ),
            )
            for group, members in group_options(self._options)
        )
        self._has_warning = any(option.is_high_resolution for option in self._options)
        self.stateChanged.emit()
