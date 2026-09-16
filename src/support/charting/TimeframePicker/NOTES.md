# TimeframePicker

Two `.qml` files sharing one `TimeframeVM`, per the user's explicit "2
widget lận đó, nếu reuse được gì thì tạo common" (2026-08-29):

- `TimeframeToolbar.qml` — the compact pill row (mockup: `1m 5m 15m 1h 1d …`),
  meant to sit in a chart header, replacing `ChartToolbar`'s fixed
  `DEFAULT_TIMEFRAMES` tuple with a user-editable pinned set.
- `TimeframePicker.qml` — the full modal grid (mockup: `CHỌN KHUNG THỜI
  GIAN`), grouped by unit, each cell showing a pin star.

They share one `TimeframeVM` instance rather than each holding its own copy
of the pinned set: pinning a timeframe in the picker must show up in the
toolbar's pills immediately, and two independently-refreshed copies of the
same set is exactly the shape `BUG-064` and `ISymbolPickerSource`'s
read/write split both trace back to (`qml-rule.md` §0.2's second bullet).

## Reuses the existing catalogue, does not re-derive it

`TimeframeVM` reads `components/timeframe_picker/catalogue.py` directly —
`TimeframeOption`, `group_options`, `options_for`, `GROUP_LABELS`, and the
newly-added `GROUP_CAPTIONS` (added to that module, not duplicated here,
per the same §0.2 rule). That module already exists specifically so a
timeframe added to the domain's `TimeFrame` enum reaches every consumer with
no second edit; this widget is another consumer, not a fork of the list.

`GROUP_CAPTIONS` is additive: `TimeframePickerOverlay` (the QtWidgets
dialog `ChartToolbar` already opens) does not read it, so adding it changed
nothing about what that dialog shows.

## The mockup's "GIÂY" section shows more than the domain has

The mockup shows `1s / 5s / 15s / 30s` under "GIÂY". `TimeFrame` (and
Binance's actual kline intervals) only has `1s` — there is no `5s`/`15s`/
`30s` timeframe anywhere in this stack (exchange, domain enum, or database
schema). `TimeframeVM` renders whatever `options_for()` actually returns, so
today's "GIÂY" section has exactly one card. Adding the other three would be
a domain-layer change (new `TimeFrame` members, verifying the exchange and
`IMarketDataRepository` actually support them) well outside "build the QML
widget" — not done here, flagged rather than either fabricated or silently
dropped without mention.

## `TimeframePicker.qml` (the modal grid) — wired into 3 screens, `EPIC-015` bậc 1

`timeframe_picker_dialog.py`'s `TimeframePickerDialog` is the `QmlOverlay`
host — Settings (`_open_default_interval_picker`), Data Management
(`_open_timeframe_picker`), and Backtest
(`backtest_modals/modals_host.py::_open_timeframe_picker`) all construct it
directly with their own `get_codes`/`get_current`, replacing
`TimeframePickerOverlay` (QtWidgets) at exactly those three call sites. No
per-screen adapter file was needed the way `BacktestTimeRangeSource` was for
time ranges — `get_codes`/`get_current` are one-line reads on every one of
the three screens, matching `EPIC-014`'s own earlier finding that Backtest's
former *private* copy of this dialog collapsed into the shared
`components/timeframe_picker` overlay with no translation logic at all.

Choosing a card closes the dialog immediately — `TimeframePickerCard.qml`'s
`onChosen` calls `vm.choose(code)` straight from the delegate, with no
separate Apply step — so the host supplies no footer buttons, the same shape
`TimezonePickerDialog` already uses on top of `SelectList.qml`.

**`TimeframePickerOverlay` (QtWidgets) is deleted** — `EPIC-015` Phase 4:
once `ChartToolbar` (`components/chart_card/chart_toolbar.py`) switched its
own "…" button to opening `TimeframePickerDialog` instead (sharing its
toolbar's `TimeframeVM`, see the section below), it was the last live
consumer (`grep -rn TimeframePickerOverlay src/ tests/` found none left).
`components/timeframe_picker/overlay.py`, its `TimeframeCard` delegate, and
their test file are gone; `components/timeframe_picker/` is catalogue data
only now (`catalogue.py`).

### The pinned-set gap for the three `from_callbacks()` screens (known,
accepted — not a persistence feature)

`TimeframeVM.get_pinned`/`set_pinned` back each grid cell's pin star. For
Settings/Data Management/Backtest's own modal-only picker (below), pinning
is cosmetic — nothing on those screens reads the pinned set except the
picker's own star, so a plain in-memory `PinnedTimeframes` per screen is
enough and stays that way. `ChartToolbar`'s own `PinnedTimeframes` (Phase 4,
see the section above) is a separate instance with a real consumer — its
own embedded toolbar pill row — and is documented in `chart_toolbar.py`
itself, not here. None of the three screens now wiring
`TimeframePickerDialog` have any persisted "pinned timeframes" concept
(checked `SettingsViewModel`, `DataManagementViewModel`, `BackTestViewModel`
directly — none hides one). Each screen's composition root backs both
callbacks with its own `PinnedTimeframes` (`timeframe_picker_dialog.py`): a
private, in-memory, non-persisted `set[str]`. Pinning a cell visibly toggles
the star for the rest of the session and resets the next time that screen
rebuilds its lazily-cached dialog instance (app restart, mainly) — not built
to survive that, on purpose. `TimeframeToolbar.qml`'s own wiring phase
(below) did give pinning a real consumer, and made a deliberate call to
still keep it in-memory rather than adding persistence in the same pass —
see that section for the reasoning.

## `TimeframeToolbar.qml` — wired into Backtest + Dev Board, `EPIC-015` Phase 4

`components/chart_card/chart_toolbar.py`'s `ChartToolbar` is the host: a
bare `QQuickWidget` embedding `TimeframeToolbar.qml` inline in `ChartCard`'s
header (same "panel beside chart" shape `qml-rule.md` §0 names, not inside
it), replacing the QtWidgets pill row + `TimeframePickerOverlay` it used to
open for "…". One construction site (`ChartCard._setup_layout()`) covers
both Backtest and Dev Board, since both build their chart area from
`ChartCard` — no second host was written.

The gap this section used to flag — two per-screen `PinnedTimeframes`
instances defeating the one-`TimeframeVM`-two-views design — is closed:
`ChartToolbar` builds exactly one `TimeframeVM` and hands it to both
`TimeframeToolbar.qml` (this widget's own context property) and to
`TimeframePickerDialog(vm)` (the constructor Phase 4 added for exactly this;
see `timeframe_picker_dialog.py`'s docstring) when the "…" button opens it.
Pinning a code from the picker updates the same `pinnedRows` the toolbar
reads — no second refresh, no drift.

`PinnedTimeframes` stays in-memory (not `ui_state`/`IStateContributor`
-persisted) and scoped to one `ChartToolbar` instance (not shared across
sibling `ChartCard`s on the same screen) — see `chart_toolbar.py`'s module
docstring for the full reasoning; short version: closing the one required
gap (shared, not doubled) does not require also solving persistence or
cross-symbol sharing, and this is `qml-rule.md` §6's highest-risk phase, not
the place to add a second, unrelated risk surface.

`TimeframeVM.set_current(code)` (added alongside this wiring) is what backs
`ChartToolbar.set_active()` — the old widget's contract of updating the
highlight without emitting a change signal, which `choose()` cannot do
since it always emits `chosen`.

## `preview.py`, colocated `tests/` — same reasons as `TimeRangePicker`

`ChartToolbar` is now a real screen host for `TimeframeToolbar.qml` (see
above), but `preview.py` is still the only place both `.qml` files render
stacked against the SAME live `TimeframeVM` with nothing else on screen
(`.\scripts\uml_preview.ps1 src/presentation/ui/qml/TimeframePicker` or
`.\scripts\preview-qml.ps1 TimeframePicker`) — useful for iterating on the
pair without a full `ChartCard`/chart around them. On a real screen, pinning
a code from `ChartToolbar`'s own picker and watching its own toolbar pills
update is exactly this preview's behaviour, live in the app; the three
`from_callbacks()` screens (Settings/Data Management/Backtest's own
modal-only picker) each still use their own, unshared `PinnedTimeframes` —
see above — so only `ChartToolbar`'s pair actually shares one instance
outside this preview. Tests are
colocated rather than in the central `tests/unit/presentation/ui/qml/` tree
`Capital`/`SelectList` use, for the same reason `TimeRangePicker`'s are:
importing `catalogue.py` already goes through `components/__init__.py`
(which needs `sagittarius_engine`), so this widget's own tests load the
`.qml` files directly into a bare `QQuickWidget` instead of through
`QmlOverlay`.
