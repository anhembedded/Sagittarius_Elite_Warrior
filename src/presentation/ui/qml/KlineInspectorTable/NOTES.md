# KlineInspectorTable

QML port of Data Management's "Tra cứu dữ liệu nến (KLine Inspector)"
modal. Same tier decision as `DatabaseStatusTable`/`TradeLogTable`
(2026-08-29/30): "dựng khung trước, đủ tính năng sau" — structural pass,
real data reused end-to-end, several things the mockup shows deferred on
purpose (see below).

## Reuses the real production conversion, not a copy

`KLineInspectorTableModel`'s own docstring already said its per-row widget
"was built for a QML delegate reading named roles per row, not for a real
per-column `QTableView`" — this widget is that QML delegate. Two additive
functions were added to that same file rather than duplicated here:

- `market_data_to_kline_row(k)` — extracted from `set_klines()`'s loop body,
  unchanged behaviour (verified: the existing 3 tests plus 2 new ones for
  the extracted/added functions all pass).
- `kline_display_row_to_qml(row)` — the plain-dict shape a QML delegate
  reads, using the exact same role names `_ROLE_NAMES` already declares.

`KlineInspectorVM` calls both; it does not re-derive a price format, a
volume abbreviation, or the bullish/bearish rule.

## One design changed on purpose, not copied from QtWidgets

`qml-rule.md` §0.2: adding a feature to an existing shape means asking
whether that shape still fits, not patching around it.

**No pagination.** `KLineInspectorTableModel` paginates in memory because a
`QWidget` per row was expensive. The fetch itself is already bounded —
`KLineInspectorCoordinator.run_inspect_klines` hardcodes `limit=10000` on
every query, matching the mockup's own "10000 nến" header — so a QML
`ListView(reuseItems: true)` virtualizes the whole shard directly, the same
way `SymbolPicker`'s `GridView` renders 1000 symbols with only the visible
cards instantiated. `KlineInspectorVM.rows` is the full list; wiring this
to a real screen later means the host supplies all 10,000 rows at once
(`DataManagementViewModel` already receives exactly that many from the
coordinator — no change needed there), not a page at a time.

## What the mockup has that this pass does not build

- **"Nhảy tới ngày" (jump-to-date).** `KLineInspectorTableModel.jump_to_date()`
  already implements this, but jumping only means something when there is
  a page to land on — with pagination gone, its role becomes "scroll the
  `ListView` to a matching row," a different (if related) piece of QML
  wiring, not the same call ported as-is. Deferred rather than half-ported.
- **"Kiểm định Dữ liệu (Audit)" button and its result banner.** Backed by a
  real query (`AuditDatabaseIntegrityQuery`) that has to actually run and
  report back — an async result this standalone widget has nowhere to put
  yet, same reasoning `DatabaseStatusTable` deferred its row actions.
- **Page-size selector (50/100/200/500).** Meaningless once pagination is
  gone — not deferred, actively dropped, since virtualization makes "how
  many rows per page" not a question this design has an answer to.

## Not yet wired into a screen

Nothing in `screens/` constructs `KlineInspectorVM` yet — Data Management
keeps rendering this table through `kline_inspector_dialog.py`
(`_kline_row.py` + `KLineInspectorTableModel`) today. `preview.py` seeds a
handful of example candles built the same way
`test_kline_inspector_table_model.py`'s `_make_candle()` does, via real
`MarketData` entities — not a fabricated dict shape.
