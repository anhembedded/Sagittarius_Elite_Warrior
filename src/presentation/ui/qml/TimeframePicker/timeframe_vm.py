"""Shared state behind `TimeframeToolbar.qml` and `TimeframePicker.qml`.

One VM, two views: the compact pill row and the full grouped grid read the
same pinned set and current code, so pinning a timeframe in one instantly
shows in the other — the reason this is one widget with two `.qml` files
sharing one ViewModel, not two separate widgets (`qml-rule.md` §0.2, user's
explicit "2 widget, common nếu reuse được").

Reuses `components/timeframe_picker/catalogue.py` for the domain-derived
grouping/labels rather than re-deriving them — the whole reason that module
takes no Qt import is so something else (this VM) can read it too, and a
timeframe added to the domain's `TimeFrame` enum lands here with no second
edit, same as it already does for `TimeframePickerOverlay`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker.catalogue import (
    GROUP_CAPTIONS,
    GROUP_LABELS,
    TimeframeOption,
    group_options,
    options_for,
)


class TimeframeVM(QObject):
    """
    @brief The catalogue narrowed to what a screen offers, with a pinned
    subset and one current code — read by both `.qml` files this widget has.

    @details Callback-constructed, not handed a screen ViewModel — same
    reasoning as `SelectListVM`/`TimeRangePickerVM`: this widget has no
    opinion about which screen owns it. `set_pinned` is a write-through
    call, not a fire-and-forget signal the host might ignore — the same
    symmetric read/write shape `ISymbolPickerSource.set_favourite` was
    given once its VM needed to persist a toggle, applied here from the
    start rather than added after the fact.
    """

    stateChanged = Signal()
    chosen = Signal(str)

    def __init__(
        self,
        *,
        get_codes: Callable[[], Sequence[str]],
        get_current: Callable[[], str],
        get_pinned: Callable[[], Sequence[str]],
        set_pinned: Callable[[str, bool], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_codes = get_codes
        self._get_current = get_current
        self._get_pinned = get_pinned
        self._set_pinned = set_pinned

        self._options: list[TimeframeOption] = []
        self._current = ""
        self._pinned: set[str] = set()

        self._pinned_rows: list[dict[str, object]] = []
        self._groups: list[dict[str, object]] = []
        self._has_warning = False

    # ------------------------------------------------------------------ #
    # QML-facing properties — all recompute together, see `_recompute`.
    # ------------------------------------------------------------------ #

    @Property("QVariantList", notify=stateChanged)
    def pinnedRows(self) -> list[dict[str, object]]:
        """One entry per pinned code, in catalogue (duration) order — the
        `TimeframeToolbar.qml` pill row reads only this."""
        return self._pinned_rows

    @Property("QVariantList", notify=stateChanged)
    def groups(self) -> list[dict[str, object]]:
        """One entry per non-empty `TimeframeGroup` — `TimeframePicker.qml`'s
        grouped grid reads only this."""
        return self._groups

    @Property(str, notify=stateChanged)
    def currentCode(self) -> str:
        return self._current

    @Property(bool, notify=stateChanged)
    def hasWarning(self) -> bool:
        """Whether any offered option is sub-minute — same condition
        `TimeframePickerOverlay._HIGH_RESOLUTION_WARNING` gates on."""
        return self._has_warning

    # ------------------------------------------------------------------ #
    # Host-facing API
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """Re-reads codes/current/pinned from the host and rebuilds both
        views. Public for a screen whose option list changes at runtime —
        same reason `TimeframePickerOverlay.refresh()` is public."""
        self._options = options_for(list(self._get_codes()))
        self._current = self._get_current()
        self._pinned = {str(code) for code in self._get_pinned()}
        self._recompute()

    @Slot(str)
    def choose(self, code: str) -> None:
        if not any(option.code == code for option in self._options):
            return
        self._current = code
        self._recompute()
        self.chosen.emit(code)

    @Slot(str)
    def togglePinned(self, code: str) -> None:
        if not any(option.code == code for option in self._options):
            return
        pin = code not in self._pinned
        if pin:
            self._pinned.add(code)
        else:
            self._pinned.discard(code)
        self._set_pinned(code, pin)
        self._recompute()

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _recompute(self) -> None:
        self._pinned_rows = [
            {
                "code": option.code,
                "current": option.code == self._current,
            }
            for option in self._options
            if option.code in self._pinned
        ]
        self._groups = [
            {
                "label": GROUP_LABELS[group],
                "caption": GROUP_CAPTIONS[group],
                "rows": [
                    {
                        "code": option.code,
                        "label": option.label,
                        "pinned": option.code in self._pinned,
                        "current": option.code == self._current,
                    }
                    for option in members
                ],
            }
            for group, members in group_options(self._options)
        ]
        self._has_warning = any(option.is_high_resolution for option in self._options)
        self.stateChanged.emit()
