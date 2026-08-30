"""`TimeframePickerDialog` — the standalone `TimeframePicker.qml`/
`TimeframeVM` pair (the modal grid only — `TimeframeToolbar.qml`'s pill row
is a separate, later, higher-risk phase of this rollout, see NOTES.md),
hosted behind `QmlOverlay`'s chrome.

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

@par The pinned-set gap (known, accepted — not built here)
`TimeframeVM` also needs `get_pinned`/`set_pinned` to back each cell's pin
star, a feature that exists only to feed `TimeframeToolbar.qml`'s pill row
(the out-of-scope sibling widget). None of the three screens wiring this
dialog today (Settings, Data Management, Backtest) have any persisted
"pinned timeframes" concept. `PinnedTimeframes` below is the accepted stand-
in: a private, in-memory, non-persisted `set[str]`, one instance per screen
composition root. Pinning a cell visibly toggles its star for the rest of
the session and resets the next time that screen rebuilds its lazily-cached
dialog instance (app restart, or the rare case a screen tears its cached
dialog down) — this is not a persistence feature to build as part of this
task, named explicitly rather than silently assumed, same pattern as
`9802853`'s Dev Board timeframe-seconds fallback.

@par Why one shared host, not three near-duplicates
`get_codes`/`get_current` are one-line reads on every one of the three
screens (`EPIC-014` already flattened Backtest's own former private copy of
this dialog into the shared `components/timeframe_picker` overlay for the
same reason — see that package's `__init__.py` docstring) — there is no
per-screen translation logic here the way `BacktestTimeRangeSource` needed
for time ranges, so a screen's composition root only has to answer "where
do these five values come from", never re-wire the chosen/close behaviour.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ..host import QmlOverlay
from .timeframe_vm import TimeframeVM

_QML = Path(__file__).with_name("TimeframePicker.qml")
_DEFAULT_TITLE = "CHỌN KHUNG THỜI GIAN"


class PinnedTimeframes:
    """Session-only pinned-timeframe set — see this module's "pinned-set
    gap" note above. A screen's composition root constructs one instance
    (never shared across screens) and passes `get`/`set` straight through
    as `TimeframePickerDialog`'s `get_pinned`/`set_pinned`."""

    def __init__(self) -> None:
        self._codes: set[str] = set()

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

    @param get_codes / get_current The screen's offered codes and its
        current one — the same two values every caller of the old
        `TimeframePickerOverlay(get_options=..., get_current=...)` already
        read, renamed to match `TimeframeVM`'s own parameter names.
    @param get_pinned / set_pinned Back the grid's pin star. See this
        module's docstring — `PinnedTimeframes` is the accepted per-screen
        stand-in until `TimeframeToolbar.qml` gives pinning a real consumer.
    """

    chosen = Signal(str)

    def __init__(
        self,
        *,
        get_codes: Callable[[], Sequence[str]],
        get_current: Callable[[], str],
        get_pinned: Callable[[], Sequence[str]],
        set_pinned: Callable[[str, bool], None],
        title: str = _DEFAULT_TITLE,
        parent: QWidget | None = None,
    ) -> None:
        self._widget_vm = TimeframeVM(
            get_codes=get_codes,
            get_current=get_current,
            get_pinned=get_pinned,
            set_pinned=set_pinned,
        )
        super().__init__(
            title, qml_file=_QML, context={"vm": self._widget_vm}, parent=parent
        )
        self.setObjectName("timeframePickerDialog")
        self.resize(560, 520)
        self._widget_vm.chosen.connect(self._on_chosen)

    def open_dialog(self) -> None:
        """Re-reads codes/current/pinned, then shows. Public for the same
        reason `TimeframePickerOverlay.refresh()`/`CapitalDialogWidget.open_dialog()`
        are: a screen's offered codes and current choice both change between
        opens of one lazily-cached dialog instance."""
        self._widget_vm.refresh()
        self.show()
        self.raise_()

    def _on_chosen(self, code: str) -> None:
        self.chosen.emit(code)
        self.accept()
