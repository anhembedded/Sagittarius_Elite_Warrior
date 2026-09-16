"""`ChartToolbar` — a chart header's compact timeframe pill row, plus the
full picker it opens. Embedded (not modal) in `ChartCard`'s header via
`ChartCard.add_to_header` — shared by both Backtest's and Dev Board's chart
headers, since both build their chart area from `ChartCard`.

`EPIC-015` Phase 4: replaces the QtWidgets pill row (fixed
`DEFAULT_TIMEFRAMES` buttons + `TimeframePickerOverlay` for "…") with
`TimeframeToolbar.qml` (embedded here, a bare `QQuickWidget`, same shape
`StatusPillWidget`/`ProgressBannerWidget` already proved for a panel
embedded directly beside — not inside — a live chart) and
`TimeframePickerDialog` (`QmlOverlay`-hosted, unchanged from Phase 1, opened
modally on the "…" button). Public surface is unchanged
(`sig_timeframe_changed`, `set_active()`) so `ChartCard._setup_layout()`,
`backtest_chart_host.py`'s `PythonBacktestChartHost`, and
`dashboard_presenter.py` need no changes at all — they still read
`card.toolbar.sig_timeframe_changed` / call `card.toolbar.set_active(...)`.

@par The one hard requirement: one `TimeframeVM`, not two
`qml/TimeframePicker/NOTES.md` flags this widget by name as the reason
`TimeframeVM` exists as ONE class shared by two `.qml` files: the toolbar's
pinned pills and the picker's pin stars must agree, instantly, without a
second refresh. This class builds exactly one `TimeframeVM` at construction
and hands the SAME instance to both `TimeframeToolbar.qml` (via this
widget's own `rootContext()`) and to the `TimeframePickerDialog` it lazily
opens (`TimeframePickerDialog(vm)`, the constructor `EPIC-015` Phase 4 added
specifically for this — see that module's docstring). Toggling a pin from
the full picker updates the SAME `pinnedRows` the embedded toolbar reads;
choosing a card there or a pill here both go through the same `vm.chosen`,
which this class listens to exactly once.

@par Design decision — pinned-state scope and persistence (qml-rule.md
§0.2's "make a reasoned call, do not default into it")
Two questions, both now resolved — the second reverses what this phase
originally shipped, recorded here rather than silently rewritten
(`qml-rule.md` §9's convention for a resolved decision):

1. **Shared between which views?** Only between one chart's own embedded
   toolbar and its own picker modal — not across sibling `ChartCard`s on the
   same screen (Backtest/Dev Board each render one `ChartCard` per symbol,
   each building its own `ChartToolbar`). The original phase framed this as
   "one `TimeframeVM` per chart" and left open whether "which timeframes I
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
   only what backs `TimeframeVM`'s `get_pinned`/`set_pinned` did, exactly as
   predicted. A bare `ChartToolbar()` with no store injected still falls
   back to the in-memory `PinnedTimeframes` this class always used —
   unpersisted, but otherwise identical to today's behaviour, the same
   fallback shape `BackTestModalsHost` uses for `SymbolPreferences`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    all_options,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeframePicker.timeframe_picker_dialog import (
    PinnedTimeframes,
    TimeframePickerDialog,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeframePicker.timeframe_vm import (
    TimeframeVM,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.embed import (
    QuickSizePolicy,
    QuickSurface,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import StyleRole

#: Re-exported for existing callers/tests (`from ...chart_toolbar import
#: DEFAULT_TIMEFRAMES`) — the value itself now lives in
#: `timeframe_pin_preferences.py` since seeding a never-seen symbol is that
#: module's job, not this constructor's. See that module's docstring for the
#: `EPIC-014`/duration-fit reasoning behind the five codes chosen.
from .timeframe_pin_preferences import DEFAULT_TIMEFRAMES, TimeframePinPreferences

_QML_FILE = (
    Path(__file__).resolve().parents[2]
    / "qml"
    / "TimeframePicker"
    / "TimeframeToolbar.qml"
)


class _ActiveTimeframe:
    """The interval this toolbar currently highlights, in one mutable box.

    A `QWidget` subclass may not set instance attributes before its Qt base
    is constructed, and `QuickSurface` takes its context objects *at*
    construction — so the `TimeframeVM` below has to exist before
    `super().__init__()`, while the value its `get_current` callback reads
    keeps changing afterwards. One shared box is the honest way to say that:
    the closure and the toolbar read and write the same object, so there is
    no second copy of "which interval is active" to drift.
    """

    __slots__ = ("code",)

    def __init__(self, code: str | None) -> None:
        self.code = code


class ChartToolbar(QuickSurface):
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
        # not take instance attributes before its Qt base is constructed,
        # and `QuickSurface` needs the two callbacks below to build the VM
        # it is handed.
        pin_preferences: TimeframePinPreferences | None = None
        if timeframe_pin_preferences is not None and symbol is not None:
            pin_preferences = timeframe_pin_preferences
            get_pinned, set_pinned = timeframe_pin_preferences.bound_to(symbol)
        else:
            fallback = PinnedTimeframes(initial=timeframes)
            get_pinned, set_pinned = fallback.get, fallback.set
        # ONE VM for both this embedded toolbar and the picker modal it
        # opens — see this module's docstring, "the one hard requirement".
        # `get_codes` offers every domain timeframe (matches the old
        # `ChartToolbar._open_picker()`'s `get_options=lambda: [option.code
        # for option in all_options()]`), not just the pinned/default
        # subset — pinning and choosing both reach codes outside
        # `DEFAULT_TIMEFRAMES`.
        #
        # Built before `super().__init__()`, because `QuickSurface` takes its
        # context properties at construction — hence `_ActiveTimeframe`, the
        # one box both this closure and the toolbar itself read (see that
        # class). `refresh()` runs first so the very first rendered frame
        # already shows the seeded pills instead of an empty row that fills
        # in a moment later, avoiding exactly the chart-adjacent flicker
        # `qml-rule.md` §6 warns this phase to watch for.
        vm = TimeframeVM(
            get_codes=lambda: [option.code for option in all_options()],
            get_current=lambda: active_state.code or "",
            get_pinned=get_pinned,
            set_pinned=set_pinned,
        )
        vm.refresh()
        # `HUG`: a compact row must hug its pills' natural width, not stretch
        # to fill whatever space `ChartCard`'s header row leaves — the
        # opposite need from every fill-the-panel host in this app. The row
        # sits on `ChartCard`'s own SURFACE, and `QuickSurface` clears the
        # scene to that token instead of to a transparent colour that renders
        # black on a real screen (`BUG-115`).
        super().__init__(
            _QML_FILE,
            surface=StyleRole.SURFACE,
            context={"vm": vm},
            size_policy=QuickSizePolicy.HUG,
            object_name="chartToolbarQuick",
            parent=parent,
        )
        self.setObjectName("chartToolbar")
        self._active_state = active_state
        self._symbol = symbol
        self._pin_preferences = pin_preferences
        self._vm = vm
        self._vm.chosen.connect(self._on_chosen)
        self._picker: TimeframePickerDialog | None = None
        self.root_object.moreRequested.connect(self._open_picker)

    def _on_chosen(self, code: str) -> None:
        """`vm.chosen` fires from either view — a pill clicked here, or a
        card chosen in the picker modal — so connecting once here, rather
        than also connecting to `self._picker.chosen`, is what keeps a
        picker choice from re-emitting `sig_timeframe_changed` twice."""
        self._active_state.code = code
        self.sig_timeframe_changed.emit(code)

    def set_active(self, timeframe: str | None) -> None:
        """Highlights `timeframe` without emitting `sig_timeframe_changed`.

        @details For a caller that already knows the new interval and only
        needs this row's own highlight to catch up — `EPIC-010D`'s restored
        interval on launch, or a Presenter's echo-back after its own change
        already fired through some other path. Delegates to
        `TimeframeVM.set_current()`, which exists for exactly this
        (`choose()` cannot be reused here: it always emits `chosen`, which
        would loop straight back into `_on_chosen`).
        """
        self._active_state.code = timeframe
        self._vm.set_current(timeframe)

    def _open_picker(self) -> None:
        """Opens the full timeframe picker, sharing this toolbar's own
        `TimeframeVM` rather than building a second one.

        @details Still a dumb component (Rule 1): it opens a chooser for the
        very thing it already chooses and emits the same signal through the
        one `vm.chosen` connection above, so no consumer learns anything new
        and neither has to duplicate the wiring. Owning the dialog here
        rather than exposing a `moreRequested`-passthrough signal is what
        keeps Backtest and Dev Board from growing two copies of it — same
        reasoning the QtWidgets original documented for `TimeframePickerOverlay`.
        """
        if self._picker is None:
            self._picker = TimeframePickerDialog(self._vm, parent=self)
        self._picker.open_dialog()
