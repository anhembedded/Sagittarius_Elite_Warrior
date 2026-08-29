# TimeRangePicker

Shared modal body for "pick a start/end instant": quick presets down the
left, two months of calendar plus TỪ/ĐẾN text fields on the right, a summary
line underneath. It generalises the mockup behind `KHOẢNG THỜI GIAN DỮ LIỆU`
(`components/date_range_picker.py`'s `pick_date_range()`, itself a bridge to
`kit/overlays/date_range_overlay.py`'s `DateRangeOverlay`) into the QML
widget shape, for every screen that needs the same picker instead of each
screen keeping its own copy (`EPIC-014`'s reason for existing).

## Not yet wired into a screen

This is a new component, built to the corrected modal idiom
(`.agents/rules/qml-rule.md` §0.1) — nothing in `screens/` constructs it yet.
`DateRangeOverlay`/`pick_date_range()` keep running unchanged for Data
Management and Dev Board; swapping either screen onto this widget is a
separate, later step (user decision 2026-08-29: "tạo cái mới, còn cái cũ kệ
nó").

## Host contract — QmlOverlay, not a self-contained Popup

Unlike `SymbolPicker`, this widget is not meant to be portable to another Qt
application — it only needs to work inside *this* app, and every screen that
will use it (Data Management, Dev Board) is still QtWidgets-hosted today. Per
`qml-rule.md` §0.1, that means the right shape is a plain layout hosted
inside `QmlOverlay` (title, subtitle, Hủy/Áp dụng chrome supplied by
`Overlay`), the same pattern `Capital`/`SelectList`/`StatGrid`/`CheckboxList`
already use — not a self-contained `Popup`. `TimeRangePicker.qml` therefore
has no root `Item`/`Popup` of its own and no fallback `vm`/`Theme` objects:
like those four, it reads the `vm`/`Theme` context properties a real
`QmlOverlay` host always sets before the file loads.

A future host wires it the same way `capital_dialog.py` wires `CapitalVM`:

```python
self._widget_vm = TimeRangePickerVM(
    get_now=lambda: datetime.now(UTC),
    get_from_text=lambda: view_model.fromDateTimeText,
    get_to_text=lambda: view_model.toDateTimeText,
    get_timeframe_seconds=lambda: view_model.activeTimeframeSeconds,
    get_timeframe_label=lambda: view_model.activeTimeframeLabel,
)
super().__init__(
    "KHOẢNG THỜI GIAN DỮ LIỆU", qml_file=_QML, context={"vm": self._widget_vm}
)
```

`get_timeframe_seconds`/`get_timeframe_label` are what let the summary read
"≈ N nến 5m" for whichever interval a screen actually has selected, instead
of the old bridge's `_MINUTES_PER_DAY` constant that always said "nến 1m"
regardless of screen state.

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
`screens/` and the sidebar). This widget has no host screen yet, so without
one it would be unrenderable by anything until that wiring exists. Run it
with `.\scripts\uml_preview.ps1 src/presentation/ui/qml/TimeRangePicker` or
`.\scripts\preview-qml.ps1 TimeRangePicker` (auto-discovered, same as any
screen). It reads the app's real `Palette`-backed `Theme` bridge — already
seeded by `preview_qml.py` before `build_preview()` runs — not a copy of the
tokens, unlike `SymbolPicker`'s own preview (that one avoids the bridge for
an unrelated reason: zero app dependency, not the Theme lookup itself).

## Tests are colocated, unlike `Capital`/`SelectList`

Those four widgets' tests live in the central `tests/unit/presentation/ui/qml/`
tree because they are tested through a real screen's `QmlOverlay` dialog
class. This widget has no such class yet (see above), and importing
`QmlOverlay` pulls in `sagittarius_engine`, a separate repo not always
present in every dev environment. Its tests instead load `TimeRangePicker.qml`
into a bare `QQuickWidget` with hand-set `vm`/`Theme` context properties —
the same technique `SymbolPicker`'s tests use, for an unrelated reason
(portability there, sidestepping an environment dependency here). Once a
real screen host exists, add the screen-level test to the central tree the
other four use; these colocated tests do not need to move.
