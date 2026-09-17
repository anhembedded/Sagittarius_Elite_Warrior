"""`ChartToolbar` — a chart header's compact timeframe pill row, plus the
full picker it opens. Embedded (not modal) in `ChartCard`'s header via
`ChartCard.add_to_header` — shared by both Backtest's and Dev Board's chart
headers, since both build their chart area from `ChartCard`.

@par Three versions, and the public surface never moved
It began as a QtWidgets pill row (fixed `DEFAULT_TIMEFRAMES` buttons plus
`TimeframePickerOverlay` behind "…"). `EPIC-015` Phase 4 replaced that with
`TimeframeToolbar.qml` embedded in a `QQuickWidget`, and `EPIC-025` PR 4.3k
brings it back to widgets (ADR D21) as `TimeframePillRow` — a checkable
`QPushButton` per pinned code, which is what a pill is. Through all three,
`sig_timeframe_changed` and `set_active()` are unchanged, so
`ChartCard._setup_layout()`, `backtest_chart_host.py`'s
`PythonBacktestChartHost` and `dashboard_presenter.py` need no changes at all.

@par The one hard requirement: one selection, not two
The pinned pills here and the pin boxes in the full picker must agree
instantly, without a second refresh — the user's own instruction (*"2 widget,
common nếu reuse được"*). So this class builds exactly one
`TimeframeSelection` and hands the SAME instance to both `TimeframePillRow`
and the `TimeframePickerDialog` it lazily opens. Pinning in the picker updates
the very `pinned_rows` this row reads; choosing a row there or a pill here both
travel through the same `selection.chosen`, which this class listens to exactly
once.

@par Design decision — pinned-state scope and persistence (qml-rule.md
§0.2's "make a reasoned call, do not default into it")
Two questions, both now resolved — the second reverses what this phase
originally shipped, recorded here rather than silently rewritten
(`qml-rule.md` §9's convention for a resolved decision):

1. **Shared between which views?** Only between one chart's own embedded
   toolbar and its own picker modal — not across sibling `ChartCard`s on the
   same screen (Backtest/Dev Board each render one `ChartCard` per symbol,
   each building its own `ChartToolbar`). The original phase framed this as
   "one selection per chart" and left open whether "which timeframes I
   pin" should instead be one preference for a whole screen. **Resolved
   (follow-up task, `EPIC-015`): per chart, keyed by the chart's own
   symbol** — a Backtest screen comparing a 1m scalp symbol against a 1d
   swing symbol wants different pins per card, exactly the trade-off the
   original docstring flagged as the reason not to default into a shared
   set.
2. ~~**In-memory, or `ui_state`/`IStateContributor`-persisted (the
   `SymbolPreferences` pattern)?** In-memory for this pass — resets on
   restart, same as every other `PinnedTimeframes` in this app today
   (Settings/Data Management/Backtest's own modal-only picker, Phase 1).
   Reasoning:
   - The one gap this phase is required to close is "shared, not doubled"
     (above) — an in-memory shared object fully closes it. Persistence is
     an independent enhancement, not a blocker for it.
   - This is `qml-rule.md` §6's highest-risk phase: the first `QQuickWidget`
     ever built as a panel beside this app's LIVE pyqtgraph chart in
     production. Wiring a brand-new `IStateContributor` (a second,
     unrelated risk surface — a new debounced write path through
     `UiStateCoordinator`) into the same change compounds risk instead of
     isolating it, exactly what the epic's own stop-condition section asks
     this phase to avoid.
   - Not silently dropped: if pinned timeframes should survive a restart,
     `ui_state`/`IStateContributor` is the confirmed right mechanism
     (`SymbolPreferences`, `components/symbol_picker/preferences.py`, is
     the existing pattern) — nothing here forecloses adding it later, and
     doing so would not change this class's public surface at all (only
     what backs `get_pinned`/`set_pinned`).~~
   **RESOLVED (follow-up task, `EPIC-015`): persisted.** User decision:
   persist now, scoped per chart as in (1). `TimeframePinPreferences`
   (`timeframe_pin_preferences.py`, this package) is the confirmed
   `IStateContributor` this docstring predicted — same structural pattern
   as `SymbolPreferences`, but `dict[str, list[str]]` keyed by symbol
   instead of two flat lists, since "which timeframes I pin" really is a
   per-chart question. `ChartToolbar`'s own public surface did not change:
   only what backs the selection's `get_pinned`/`set_pinned` did, exactly as
   predicted. A bare `ChartToolbar()` with no store injected still falls
   back to the in-memory `PinnedTimeframes` this class always used —
   unpersisted, but otherwise identical to today's behaviour, the same
   fallback shape `BackTestModalsHost` uses for `SymbolPreferences`.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    PinnedTimeframes,
    TimeframePickerDialog,
    TimeframePillRow,
    TimeframeSelection,
    all_options,
)

#: Re-exported for existing callers/tests (`from ...chart_toolbar import
#: DEFAULT_TIMEFRAMES`) — the value itself now lives in
#: `timeframe_pin_preferences.py` since seeding a never-seen symbol is that
#: module's job, not this constructor's. See that module's docstring for the
#: `EPIC-014`/duration-fit reasoning behind the five codes chosen.
from .timeframe_pin_preferences import DEFAULT_TIMEFRAMES, TimeframePinPreferences


class _ActiveTimeframe:
    """The interval this toolbar currently highlights, in one mutable box.

    The `TimeframeSelection` below is built from closures that have to read
    "which interval is active" long after construction, and a `QWidget`
    subclass may not set instance attributes before its Qt base exists. One
    shared box is the honest way to say that: the closure and the toolbar read
    and write the same object, so there is no second copy to drift.

    `EPIC-025` PR 4.3k removed the *other* half of the reason this class
    existed — `QuickSurface` took its context objects at construction, forcing
    the selection to exist before `super().__init__()`. A plain `QWidget` has
    no such constraint, but the closures still do, so the box stays.
    """

    __slots__ = ("code",)

    def __init__(self, code: str | None) -> None:
        self.code = code


class ChartToolbar(QWidget):  # base-exempt: a container, not a surface
    """
    @brief Compact timeframe pill row for a `ChartCard` header, plus the
    full picker its "…" affordance opens.

    @details Public surface unchanged from the QtWidgets original it
    replaces: emits `sig_timeframe_changed(interval)` when a pill (here or
    in the full picker) is chosen, and `set_active()` lets an external
    caller (`EPIC-010D`'s restored interval, a Presenter's own change
    already handled elsewhere) sync the highlight without re-triggering the
    signal. Still a dumb component (Rule 1): decides nothing about what an
    interval change means, only reports it.
    """

    sig_timeframe_changed = Signal(str)

    def __init__(
        self,
        timeframes: Sequence[str] = DEFAULT_TIMEFRAMES,
        active: str | None = None,
        parent: QWidget | None = None,
        *,
        symbol: str | None = None,
        timeframe_pin_preferences: TimeframePinPreferences | None = None,
    ) -> None:
        """@param symbol / timeframe_pin_preferences Scope the pinned set to
        one chart. Both must be given together — `ChartCard` passes its own
        `self.symbol` alongside whatever store it was injected (see
        `ChartCard.__init__`). Either left as `None` (every existing bare
        `ChartToolbar()` caller: previews, unit tests) falls back to the
        private, unpersisted `PinnedTimeframes` this class has always used —
        seeded from `timeframes`, exactly as before persistence existed."""
        active_state = _ActiveTimeframe(
            active or (timeframes[0] if timeframes else None)
        )
        # See this module's docstring, design-decision §1/§2 (RESOLVED):
        # scoped to this chart's own symbol through the injected store when
        # both are given; otherwise the same private, in-memory
        # `PinnedTimeframes` this class always used, seeded with the
        # constructor's own `timeframes` so a fresh chart header is not an
        # empty row plus a lone "…" button.
        # Locals until after `super().__init__()`: a `QWidget` subclass may
        # not take instance attributes before its Qt base is constructed, and
        # the two callbacks below are what the selection is built from.
        pin_preferences: TimeframePinPreferences | None = None
        if timeframe_pin_preferences is not None and symbol is not None:
            pin_preferences = timeframe_pin_preferences
            get_pinned, set_pinned = timeframe_pin_preferences.bound_to(symbol)
        else:
            fallback = PinnedTimeframes(initial=timeframes)
            get_pinned, set_pinned = fallback.get, fallback.set
        # ONE selection for both this row and the picker it opens — see this
        # module's docstring, "the one hard requirement". `get_codes` offers
        # every domain timeframe rather than the pinned/default subset, because
        # pinning and choosing both reach codes outside `DEFAULT_TIMEFRAMES`.
        selection = TimeframeSelection(
            get_codes=lambda: [option.code for option in all_options()],
            get_current=lambda: active_state.code or "",
            get_pinned=get_pinned,
            set_pinned=set_pinned,
        )
        selection.refresh()

        super().__init__(parent)
        self.setObjectName("chartToolbar")
        self._active_state = active_state
        self._symbol = symbol
        self._pin_preferences = pin_preferences
        self._selection = selection
        self._selection.chosen.connect(self._on_chosen)
        self._picker: TimeframePickerDialog | None = None

        # A compact row hugs its pills rather than stretching across whatever
        # space `ChartCard`'s header leaves; `TimeframePillRow` carries that
        # size policy, and this layout only has to not fight it.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._row = TimeframePillRow(selection)
        self._row.more_requested.connect(self._open_picker)
        layout.addWidget(self._row)

    def _on_chosen(self, code: str) -> None:
        """`selection.chosen` fires from either view — a pill clicked here, or
        a row chosen in the picker — so connecting once here, rather than also
        connecting to `self._picker.chosen`, is what keeps a picker choice from
        re-emitting `sig_timeframe_changed` twice."""
        self._active_state.code = code
        self.sig_timeframe_changed.emit(code)

    def set_active(self, timeframe: str | None) -> None:
        """Highlights `timeframe` without emitting `sig_timeframe_changed`.

        @details For a caller that already knows the new interval and only
        needs this row's own highlight to catch up — `EPIC-010D`'s restored
        interval on launch, or a Presenter's echo-back after its own change
        already fired through some other path. Delegates to
        `TimeframeSelection.set_current()`, which exists for exactly this
        (`choose()` cannot be reused here: it always emits `chosen`, which
        would loop straight back into `_on_chosen`).
        """
        self._active_state.code = timeframe
        self._selection.set_current(timeframe)

    def _open_picker(self) -> None:
        """Opens the full timeframe picker, sharing this toolbar's own
        `TimeframeSelection` rather than building a second one.

        @details Still a dumb component (Rule 1): it opens a chooser for the
        very thing it already chooses and emits the same signal through the
        one `vm.chosen` connection above, so no consumer learns anything new
        and neither has to duplicate the wiring. Owning the dialog here
        rather than exposing a `moreRequested`-passthrough signal is what
        keeps Backtest and Dev Board from growing two copies of it — same
        reasoning the QtWidgets original documented for `TimeframePickerOverlay`.
        """
        if self._picker is None:
            self._picker = TimeframePickerDialog(self._selection, parent=self)
        self._picker.open_dialog()
