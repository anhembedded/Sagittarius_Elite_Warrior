# StatCardRow

`EPIC-015` Phase 4 — the dynamic list wrapper `kit/StatCard.qml`'s own
`NOTES.md` predicted a future host would need ("which slot a future host
uses for which card is that host's decision, not this component's"). Wires
`kit/StatCard.qml` into `BackTestTopPanel`'s primary stat-cards row
(`BackTestViewModel.primaryStatCards`), replacing per-run construction/
teardown of the QtWidgets `StatCard` (`kit/surfaces/stat_card.py`).

## Why a directory of its own, not another `kit/` file

`kit/` primitives are "pure QML, no Python VM" (`kit/NOTES.md`) because
every value they render is already computed by whichever screen ViewModel
supplies it. This widget cannot make that claim: `primaryStatCards` still
carries raw `Tone` enum members, and QML cannot read a Python `Enum`
directly — see `stat_card_row_vm.py`. A widget that needs its own VM lives
in its own `<Widget>/` directory next to that VM (`qml-rule.md` §1), the
same shape `StatGrid`/`MetricsDetailPanel` already use — `kit/` stays the
"nothing to derive" tier.

## `caption` is unused here, on purpose

`kit/StatCard.qml` keeps both `badgeText` and `caption` slots (its own
`NOTES.md`: "which slot a future host uses for which card is that host's
decision"). `stat_cards_to_qml()`
(`backtest/logic/performance_metrics_view.py`) only ever produces
`badgeText`/`badgeTone` — no `StatCardData` field maps to a caption line —
so `StatCardRowVM.refresh()` does not set one; `StatCard.qml`'s caption
`Text` stays hidden (`visible: root.caption !== ""`), matching the
QtWidgets `StatCard.set_badge()` call site this replaces, which never set
one either.

## Rebuild-frequency investigation (`qml-rule.md` §4.2's risk, checked
against both the real call sites and the actual C++ delegate identity)

Confirmed with a throwaway script holding each delegate's C++ pointer
(`shiboken6.getCppPointer()`) across two `refresh()` calls: changing even
one card's `value` out of four causes **every** delegate to get a new C++
`QQuickItem` instance, not just the one whose data changed — the exact
whole-row rebuild `qml-rule.md` §4.2 documents for `CheckboxList`/
`SelectList`, confirmed here too, not assumed. (A refresh with byte-for-byte
*identical* data reuses the same instances — Qt's array-model diffing
short-circuits a true no-op — but that case never happens in production:
`BackTestViewModel.primaryStatCards` is only ever replaced with genuinely
different content, see below, or cleared to `[]`.)

That destroy-and-recreate cost would be a real problem if it fired every
progress tick next to a live chart. It does not, here: grepping every
`BackTestViewModel.set_stat_cards()` call site
(`backtest_presenter.py`) finds exactly three, all discrete run-outcome
events, none inside the progress-tick path
(`_on_backtest_progress_for_action`/`_on_sync_progress_for_action`, which
only touch `backtestProgressPercent`/`syncProgressPercent` — a *different*
signal, not connected to `_sync_stat_cards()`):

- `_on_backtest_succeeded` — once, when a run finishes (populates the row).
- `_on_backtest_empty` — once, when a run finds no historical data at all
  (clears the row).
- `_on_backtest_failed` — once, when a run raises (clears the row).

So the `Repeater` rebuilds at most a handful of times per backtest run —
at the same three moments the old QtWidgets `_sync_stat_cards()` also fully
tore down and rebuilt every `StatCard` widget (it looped
`layout.takeAt(0)` + `deleteLater()` before constructing new ones,
unconditionally, every call) — not once per animation frame while a run is
progressing. **No new performance risk relative to the widget this
replaces**; the chart's own frame rate is driven by its own repaint path,
untouched by either version of this row.

## Natural, non-stretched widths

`StatCardRow.qml`'s `Repeater` delegates get no `Layout.fillWidth` —
deliberately, to match the `QHBoxLayout` this replaces
(`backtest_top_panel.py`'s old `_build_stat_cards_row()`/`_sync_stat_cards()`
never gave a card a stretch factor and never appended a trailing
`addStretch()`). Cards pack left at their own content width; leftover
horizontal space stays empty on the right in both versions.

## Host is callback-constructed, in `qml/`, not `screens/backtest/`

`StatCardRowWidget` takes a `get_cards` callback rather than a
`BackTestViewModel` reference (`qml-rule.md` §1.1), so it carries no
dependency on `screens/backtest/` — the reverse import
(`backtest_top_panel.py` importing this widget) is the only direction this
rollout uses anywhere. This differs from `DatabaseStatusPanel`
(`screens/data_management/data_management_widgets/`), which lives in the
*screen's* package instead: that panel takes a real
`DatabaseStatusTableModel` type from the screens layer, so putting it in
`qml/` would have created the dependency the other way around. This widget
has no such type to take, so it stays in `qml/` like `TimeRangePicker`/
`TimeframePicker`'s own dialog hosts.
