"""`TimeframePickerDialog` — the standalone `TimeframePicker.qml`/
`TimeframeVM` pair (the modal grid only — `TimeframeToolbar.qml`'s pill row
is a separate widget, see NOTES.md), hosted behind `QmlOverlay`'s chrome.

@par Choose-and-close-immediately, no footer buttons
`TimeframePickerCard.qml`'s `onChosen` calls `vm.choose(code)` straight from
the delegate — there is no separate Apply step in `TimeframePicker.qml`
itself, exactly like `SelectList.qml`'s rows do for `TimezonePickerDialog`.
So this host supplies no `_build_buttons()` override at all:
`Overlay`'s own default (an empty row) is exactly right, and the native
dialog close (X) / Escape is how a caller backs out without choosing — the
same as `TimezonePickerDialog`. `Capital`/`TimeRangePicker`'s Hủy/Áp dụng
footer does not apply here; that shape exists only where the `.qml` itself
defers committing a choice until an explicit Apply, which this one does not.

@par Two ways in: a fresh `TimeframeVM`, or an existing one to share
`EPIC-015` Phase 4 (`ChartToolbar`, see `components/chart_card/
chart_toolbar.py`) is the first caller that needs its "…" button to open
this exact dialog sharing the SAME `TimeframeVM` instance its embedded
`TimeframeToolbar.qml` already reads and writes — not a second VM wired to
the same callbacks, which would be two independent copies of the pinned set
and current code (`NOTES.md`'s originally-flagged gap, and `qml-rule.md`
§0.2's second bullet: two places holding the same truth is exactly the shape
that drifts). So the primary constructor now takes a `TimeframeVM` directly.
Every caller before Phase 4 (Settings, Data Management, Backtest's own
modal-only picker) is the *other* shape — the picker is their only consumer
of timeframe state, so there is nothing to share a VM with — and keeps
working unchanged through `from_callbacks()`, a thin classmethod that builds
a private `TimeframeVM` from the same four callbacks the old single
constructor took.

@par Why one shared host, not three (now four) near-duplicates
`get_codes`/`get_current` are one-line reads on every one of the three
`from_callbacks()` screens (`EPIC-014` already flattened Backtest's own
former private copy of this dialog into the shared `components/
timeframe_picker` overlay for the same reason — see that package's
`__init__.py` docstring) — there is no per-screen translation logic here the
way `BacktestTimeRangeSource` needed for time ranges, so a screen's
composition root only has to answer "where do these four values come from",
never re-wire the chosen/close behaviour.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ..host import QmlOverlay
from .timeframe_vm import TimeframeVM

_QML = Path(__file__).with_name("TimeframePicker.qml")
_DEFAULT_TITLE = "CHỌN KHUNG THỜI GIAN"


class PinnedTimeframes:
    """Session-only pinned-timeframe set.

    @details A screen's composition root constructs one instance (never
    shared across screens) and passes `get`/`set` straight through as
    `TimeframeVM`'s `get_pinned`/`set_pinned` (directly, or via
    `TimeframePickerDialog.from_callbacks()`). In-memory and non-persisted:
    pinning a cell visibly toggles its star for the rest of the session and
    resets on the next app restart — see `chart_toolbar.py`'s module
    docstring for why `EPIC-015` Phase 4 (the first consumer where the
    pinned set drives a screen's default visible pills, not just a picker's
    cosmetic star) still keeps this in-memory rather than moving it onto
    `ui_state`/`IStateContributor`.

    @param initial Codes considered pinned from construction — empty by
        default (every `from_callbacks()` caller before Phase 4: a picker
        with no toolbar has no need for a non-empty starting set). Phase 4
        passes `ChartToolbar.DEFAULT_TIMEFRAMES` so a freshly-built chart
        header's pill row starts non-empty instead of pinning nothing and
        showing only the "…" button.
    """

    def __init__(self, initial: Iterable[str] = ()) -> None:
        self._codes: set[str] = set(initial)

    def get(self) -> list[str]:
        return sorted(self._codes)

    def set(self, code: str, pinned: bool) -> None:
        if pinned:
            self._codes.add(code)
        else:
            self._codes.discard(code)


class TimeframePickerDialog(QmlOverlay):
    """
    @brief Choose a candle interval. Chrome is `Overlay` (via `QmlOverlay`),
    body is `TimeframePicker.qml`, rules are `TimeframeVM`.

    @param vm The `TimeframeVM` this dialog reads and writes. Construct it
        yourself (and keep the reference) when something else must share
        it — `ChartToolbar` is the one caller that does. Everyone else
        should use `from_callbacks()` instead of building a `TimeframeVM`
        by hand.
    """

    chosen = Signal(str)

    def __init__(
        self,
        vm: TimeframeVM,
        *,
        title: str = _DEFAULT_TITLE,
        parent: QWidget | None = None,
    ) -> None:
        self._widget_vm = vm
        super().__init__(
            title, qml_file=_QML, context={"vm": self._widget_vm}, parent=parent
        )
        self.setObjectName("timeframePickerDialog")
        self.resize(560, 520)
        self._widget_vm.chosen.connect(self._on_chosen)

    @classmethod
    def from_callbacks(
        cls,
        *,
        get_codes: Callable[[], Sequence[str]],
        get_current: Callable[[], str],
        get_pinned: Callable[[], Sequence[str]],
        set_pinned: Callable[[str, bool], None],
        title: str = _DEFAULT_TITLE,
        parent: QWidget | None = None,
    ) -> TimeframePickerDialog:
        """Builds a private `TimeframeVM` from four screen callbacks — the
        shape every caller before `EPIC-015` Phase 4 uses, where this
        dialog is the only consumer of timeframe state and there is no
        toolbar to share a `TimeframeVM` with.

        @param get_codes / get_current The screen's offered codes and its
            current one — the same two values every caller of the old
            `TimeframePickerOverlay(get_options=..., get_current=...)`
            (QtWidgets, deleted in Phase 4) already read, renamed to match
            `TimeframeVM`'s own parameter names.
        @param get_pinned / set_pinned Back the grid's pin star — typically
            a screen-local `PinnedTimeframes`.
        """
        vm = TimeframeVM(
            get_codes=get_codes,
            get_current=get_current,
            get_pinned=get_pinned,
            set_pinned=set_pinned,
        )
        return cls(vm, title=title, parent=parent)

    def open_dialog(self) -> None:
        """Re-reads codes/current/pinned, then shows. Public for the same
        reason `CapitalDialogWidget.open_dialog()` is: a screen's offered
        codes and current choice both change between opens of one
        lazily-cached dialog instance."""
        self._widget_vm.refresh()
        self.show()
        self.raise_()

    def _on_chosen(self, code: str) -> None:
        self.chosen.emit(code)
        self.accept()
