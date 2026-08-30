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

**`TimeframePickerOverlay` (QtWidgets) is not deleted.** `ChartToolbar`
(`components/chart_card/chart_toolbar.py`) — the chart-header pill row that
`TimeframeToolbar.qml` is eventually meant to replace — still opens it for
its own "…" (more) button, on both Backtest's and Dev Board's live charts.
That migration is exactly the higher-risk `TimeframeToolbar.qml` phase this
NOTES.md file already called out as separate and later; it was left alone,
not folded into this task.

### The pinned-set gap (known, accepted — not a persistence feature)

`TimeframeVM.get_pinned`/`set_pinned` back each grid cell's pin star, a
feature that exists to feed `TimeframeToolbar.qml`'s pill row — the
out-of-scope sibling widget above. None of the three screens now wiring
`TimeframePickerDialog` have any persisted "pinned timeframes" concept
(checked `SettingsViewModel`, `DataManagementViewModel`, `BackTestViewModel`
directly — none hides one). Each screen's composition root backs both
callbacks with its own `PinnedTimeframes` (`timeframe_picker_dialog.py`): a
private, in-memory, non-persisted `set[str]`. Pinning a cell visibly toggles
the star for the rest of the session and resets the next time that screen
rebuilds its lazily-cached dialog instance (app restart, mainly) — not built
to survive that, on purpose, until `TimeframeToolbar.qml`'s own wiring phase
gives pinning a real, persisted consumer worth building state for.

## `TimeframeToolbar.qml` — still not wired into a screen

Nothing in `screens/` constructs `TimeframeVM` for the toolbar pill row yet.
`ChartToolbar` (QtWidgets) keeps running unchanged for Backtest and Dev
Board — same "tạo cái mới, còn cái cũ kệ nó" default as `TimeRangePicker`
before its own wiring phase. A future host wires `TimeframeVM` the same way
`capital_dialog.py` wires `CapitalVM`: construct it with callbacks
reading/writing the screen's own pinned-timeframes state — and this is where
that state needs a real home, since two per-screen `PinnedTimeframes`
instances (one behind the picker, one behind the toolbar) would defeat the
one-`TimeframeVM`-two-views design this file's opening section describes —
pass it as the `vm` context property to a `TimeframeToolbar.qml`-hosting
`QQuickWidget` and, separately, to the *same* `TimeframePickerDialog` already
built here, opened on `TimeframeToolbar`'s `moreRequested()`.

## `preview.py`, colocated `tests/` — same reasons as `TimeRangePicker`

No screen host exists yet for `TimeframeToolbar.qml` (the picker has three
now, see above), so `preview.py` is still the only way to see the toolbar
pill row render at all, and the only way to see both `.qml` files sharing
one live `TimeframeVM` at once
(`.\scripts\uml_preview.ps1 src/presentation/ui/qml/TimeframePicker` or
`.\scripts\preview-qml.ps1 TimeframePicker`) — it builds both widgets
stacked, so pinning a card in the picker and watching the toolbar's pills
update is visible in one window (the three real screen hosts each use their
own, unshared `PinnedTimeframes` — see above — so this side-by-side view is
`preview.py`-only, not reproducible from any real screen today). Tests are
colocated rather than in the central `tests/unit/presentation/ui/qml/` tree
`Capital`/`SelectList` use, for the same reason `TimeRangePicker`'s are:
importing `catalogue.py` already goes through `components/__init__.py`
(which needs `sagittarius_engine`), so this widget's own tests load the
`.qml` files directly into a bare `QQuickWidget` instead of through
`QmlOverlay`.
