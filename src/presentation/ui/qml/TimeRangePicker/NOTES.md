# TimeRangePicker

Shared modal body for "pick a start/end instant": quick presets down the
left, two months of calendar plus TỪ/ĐẾN text fields on the right, a summary
line underneath. It generalises the mockup behind `KHOẢNG THỜI GIAN DỮ LIỆU`
(`components/date_range_picker.py`'s `pick_date_range()`, itself a bridge to
`kit/overlays/date_range_overlay.py`'s `DateRangeOverlay`) into the QML
widget shape, for every screen that needs the same picker instead of each
screen keeping its own copy (`EPIC-014`'s reason for existing).

## Wired into three screens (`EPIC-015` bậc 1)

`time_range_picker_dialog.py` (this directory) is the shared host —
`TimeRangePickerDialog(QmlOverlay)` — every screen below constructs
directly:

- **Data Management** (`data_management_widgets/time_range_card.py`,
  `TimeRangeCardWidget._on_pick_range()`) — timeframe-aware via
  `set_timeframe_source()`, wired to the screen's real `selectedInterval`.
- **Dev Board** (`dashboard/dev_board_panel.py`,
  `DevBoardPanel._on_pick_range()`) — `DashboardQmlViewModel` has no
  per-timeframe concept this panel can read, so the summary uses a
  documented `1m`/60s fallback constant, not a live value.
- **Backtest** (`backtest/backtest_modals/time_range_picker_dialog.py`,
  `TimeRangePickerDialogWidget`) — the pure-logic adapter
  `BacktestTimeRangeSource` resolves the screen's *effective* current range
  through whichever preset is active (`resolve_time_range`), and an applied
  pair is written back as `TimeRangePreset.CUSTOM` — an explicit start/end
  coming out of the picker already means "Tuỳ chỉnh" on that screen.

`pick_date_range()`/`components/date_range_picker.py` — the old QtWidgets
bridge all three used before this — is deleted; nothing referenced it once
these three call sites moved (`kit/overlays/date_range_overlay.py`'s
`DateRangeOverlay`/`RangePreset` are untouched, general-purpose engine
primitives with no dependency on this widget existing).

## Host contract — QmlOverlay, not a self-contained Popup

Unlike `SymbolPicker`, this widget is not meant to be portable to another Qt
application — it only needs to work inside *this* app, and every screen that
uses it (Data Management, Dev Board, Backtest) is still QtWidgets-hosted
today. Per `qml-rule.md` §0.1, that means the right shape is a plain layout hosted
inside `QmlOverlay` (title, subtitle, Hủy/Áp dụng chrome supplied by
`Overlay`), the same pattern `Capital`/`SelectList`/`StatGrid`/`CheckboxList`
already use — not a self-contained `Popup`. `TimeRangePicker.qml` therefore
has no root `Item`/`Popup` of its own and no fallback `vm`/`Theme` objects:
like those four, it reads the `vm`/`Theme` context properties a real
`QmlOverlay` host always sets before the file loads.

Unlike `Capital`/`SelectList`/`StatGrid`/`CheckboxList` — each hand-built
per screen — `time_range_picker_dialog.py` in this directory IS that host,
already built and shared: three screens each just answer "where do these
five `get_*` values come from on my ViewModel" rather than re-wiring the
footer/Apply-enable/refresh-on-open behaviour three times
(`qml-rule.md` §0.2). A screen's own composition root looks like:

```python
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeRangePicker.time_range_picker_dialog import (
    TimeRangePickerDialog,
)

dialog = TimeRangePickerDialog(
    get_from_text=lambda: view_model.fromDateTime,
    get_to_text=lambda: view_model.toDateTime,
    get_timeframe_seconds=lambda: ...,  # real source if the screen has one
    get_timeframe_label=lambda: ...,
)
dialog.applied.connect(...)  # (start_text, end_text)
dialog.open_dialog()  # refresh() + show() + raise_()
```

`get_timeframe_seconds`/`get_timeframe_label` are what let the summary read
"≈ N nến 5m" for whichever interval a screen actually has selected, instead
of the old bridge's `_MINUTES_PER_DAY` constant that always said "nến 1m"
regardless of screen state — Data Management and Backtest both wire a real
source; Dev Board has none to wire (see above) and passes the same "1m"
fallback the old bridge always used, now a named constant instead of silent.

## Three things the mockup added over `DateRangeOverlay`/`pick_date_range()`

User decision 2026-08-29, "xây đủ cả 3": all three are implemented in
`TimeRangePickerVM`, not deferred.

1. **Two more presets** — "Toàn bộ lịch sử" and "Tuỳ chỉnh" are now entries
   in the same preset list, not special-cased UI states. "Toàn bộ lịch sử"
   resolves to `(None, None)` — the same "no limit" convention
   `backtest/logic/time_range_preset.py`'s `resolve_time_range` already uses
   for `ALL_HISTORY`, so a host applying it needs no new handling on its end.
2. **TỪ/ĐẾN fields inside the dialog itself**, editable, always visible —
   `pick_date_range()` only accepted seed text *before* opening the
   calendar; typing and clicking now write the same two fields, matching
   `TimeRangeCardWidget`'s existing "typing and clicking must not be
   distinguishable to the ViewModel" rule.
3. **Timeframe-aware candle estimate** via the two `get_timeframe_*`
   callbacks above.

**Simplification versus the mockup's pixel layout:** the mockup shows date
and time-of-day as two separate boxes per side. This implementation keeps
one `"yyyy-MM-dd HH:mm"` text field per side (`vm.fromText`/`vm.toText`) —
the underlying value already carries the time-of-day (`selectDay` preserves
whatever time was already set, `TODAY`/`7d`/... presets use the real current
time, not midnight), so splitting the single field into two boxes later is a
`.qml`-only change, not a `TimeRangePickerVM` one.

## `preview.py` exists here, unlike `Capital`/`SelectList`

Those four widgets have no `preview.py` of their own — nothing needs one,
since they're only ever seen through their host screen's preview (and the
guard test, `test_preview_fixtures_exist.py`, only requires one for
`screens/` and the sidebar). Kept here even now that a real host exists
(unlike `preview.py`'s original reason for existing, "no host screen yet")
because it stays the cheapest way to see the body render with zero screen
ViewModel to construct — `.\scripts\uml_preview.ps1
src/presentation/ui/qml/TimeRangePicker` or `.\scripts\preview-qml.ps1
TimeRangePicker` (auto-discovered, same as any screen). It reads the app's
real `Palette`-backed `Theme` bridge — already seeded by `preview_qml.py`
before `build_preview()` runs — not a copy of the tokens, unlike
`SymbolPicker`'s own preview (that one avoids the bridge for an unrelated
reason: zero app dependency, not the Theme lookup itself).

## Tests: colocated VM/`.qml` tests, plus a central host test now that one exists

`SelectList`/`CheckboxList`/`StatGrid`/`Capital`'s tests live in the central
`tests/unit/presentation/ui/qml/` tree because they are tested through a
real screen's `QmlOverlay` dialog class. This widget's own host,
`time_range_picker_dialog.py`, now exists too — its render/interaction
coverage is `tests/unit/presentation/ui/qml/test_time_range_picker_dialog_host.py`,
covering both the generic `TimeRangePickerDialog` and Backtest's
`TimeRangePickerDialogWidget` composition root — following that same
convention. What stays colocated here, unmoved, are the two tests that
predate any host and importing `QmlOverlay`, which pulls in
`sagittarius_engine`, a separate repo not always present in every dev
environment: `TimeRangePickerVM`'s own rules (no `QApplication` at all) and
the standalone `.qml`'s render/interaction behaviour, loaded into a bare
`QQuickWidget` with hand-set `vm`/`Theme` context properties —
the same technique `SymbolPicker`'s tests use, for an unrelated reason
(portability there, sidestepping an environment dependency here). These
colocated tests did not need to move once the host arrived, per the plan
recorded here before it existed — only the new host-level test was added
alongside them, in the central tree.
