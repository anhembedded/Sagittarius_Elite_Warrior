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

## Not yet wired into a screen

Nothing in `screens/` constructs `TimeframeVM` yet. `ChartToolbar` and
`TimeframePickerOverlay` (QtWidgets) keep running unchanged for Backtest and
Dev Board — same "tạo cái mới, còn cái cũ kệ nó" default as `TimeRangePicker`.
A future host wires `TimeframeVM` the same way `capital_dialog.py` wires
`CapitalVM`: construct it with callbacks reading/writing the screen's own
pinned-timeframes state (new state this app does not persist today — the
five pills were a hardcoded constant, never a per-user choice), pass it as
the `vm` context property to a `TimeframeToolbar.qml`-hosting `QQuickWidget`
and, separately, to a `QmlOverlay`-hosted `TimeframePicker.qml` opened on
`TimeframeToolbar`'s `moreRequested()`.

## `preview.py`, colocated `tests/` — same reasons as `TimeRangePicker`

No screen host exists yet, so `preview.py` is the only way to see either
widget render (`.\scripts\uml_preview.ps1 src/presentation/ui/qml/TimeframePicker`
or `.\scripts\preview-qml.ps1 TimeframePicker`) — it builds both widgets
sharing one `TimeframeVM`, stacked, so pinning a card in the picker and
watching the toolbar's pills update is visible in one window. Tests are
colocated rather than in the central `tests/unit/presentation/ui/qml/` tree
`Capital`/`SelectList` use, for the same reason `TimeRangePicker`'s are:
importing `catalogue.py` already goes through `components/__init__.py`
(which needs `sagittarius_engine`), so this widget's own tests load the
`.qml` files directly into a bare `QQuickWidget` instead of through
`QmlOverlay`.
