# TradeLogTable

QML port of Backtest's "Danh sách lệnh" tab. Same tier decision as
`DatabaseStatusTable` (2026-08-29): "dựng khung trước, đủ tính năng sau" —
structural pass, real data and real formatting reused end-to-end, several
things the mockup shows deferred on purpose (see below).

## Reuses the existing pure logic, not a copy

`TradeLogVM` calls straight into `backtest/logic/trade_log_filter.py`
(`TradeLogFilter`, `filter_trade_log_rows`) and `backtest/logic/trade_log_row.py`
(`trade_log_rows_to_qml`) — the exact functions `BackTestTradeLogsPanel`
(QtWidgets) already runs and already ships tests for. Nothing here
re-derives a PnL colour, a duration string, or a filter's membership rule.

One addition was made to the shared function itself, not duplicated here:
`trade_log_row_to_qml` now also returns `sideLabel` ("LONG"/"SHORT") and
`sideIsLong` — `positionLabel` already named the side in a Vietnamese
sentence ("vị thế mua"), but the mockup's LOẠI column needs the bare word
plus a colour flag, which nothing exposed before. Additive: the QtWidgets
row widget does not read either new key, so it renders unchanged.

## Two designs changed on purpose, not copied from QtWidgets

`qml-rule.md` §0.2: adding a feature to an existing shape means asking
whether that shape still fits, not patching around it. Both of these are
`TradeLogVM` doing something the QtWidgets panel does not, deliberately:

1. **No pagination.** `trade_log_pagination.py` exists because instantiating
   a `QWidget` per row was expensive at Backtest's real scale ("hàng nghìn"
   — that module's own comment). A QML `ListView(reuseItems: true)`
   virtualizes instead, the same way `SymbolPicker`'s `GridView` renders
   1000 symbols with only the visible cards instantiated. `TradeLogVM.rows`
   is the full filtered list; wiring this to a real screen later means
   `BackTestViewModel` needs an unpaginated "all filtered rows" source, not
   today's per-page one — a real, small change on the host side when that
   wiring happens, not a silent assumption.
2. **Per-filter counts on the tabs.** Today's tabs (`_filter_tab_button.py`)
   show a label only. The mockup adds "· N" per tab; each count is one more
   call to `filter_trade_log_rows`, already tested, not new filtering logic.

## What the mockup has that this pass does not build

- **Search** ("Tìm theo mã, ngày...") and **Export** — both have working
  pure logic behind them already (`search_trade_log_rows`,
  `requestTradeLogExport`'s existing wiring), deferred for the same reason
  `DatabaseStatusTable` deferred its search box: an unwired control that
  visibly does nothing was judged worse than adding it once, wired, later.
- **Column sort** — the mockup's footer hint ("nhấn tiêu đề cột để sắp
  xếp") names it; not rendered here, so nothing advertises it.
- **"Nhật ký Backtest"** — the mockup's second tab. This is not a second
  trade dataset: in the real screen it is `AppLogPanel` showing
  `BackTestViewModel.log_model` (a live event log), a different widget
  entirely from the trade table. Out of scope for this component; if it
  gets a QML port, it is its own widget, not a mode of this one.

## Row expand — added 2026-08-30, user decision

Originally deferred alongside column sort, then asked for explicitly once
the other tables were done. Clicking a row (or its chevron) calls
`vm.toggleExpanded(index)`, which flips one trade's membership in a
`set[int]` keyed by the stable `TradeLogRow.index` — not by list position,
so a row's expanded state survives a filter-tab switch that moves it
around (`test_expanded_state_survives_a_filter_change`). The expanded
section reads `entryReasonText`/`exitReasonText`/`durationText`/
`metadataItems` — all four already existed on `trade_log_row_to_qml`'s
output for BOT-045's QtWidgets expand row; nothing new was computed for
this.

**One exact-wording gap versus the mockup, not silently matched:** the
mockup's badges read "Thời lượng 12 phút", "R -0.4R", "Phí 9.90 USD" — the
first is `durationText` rendered as a badge (built here), but "R" and
"Phí" are not fields `TradeLogRow`/`trade_log_row_to_qml` know about today.
They render generically through `metadataItems` ("tùy vào chiến thuật" —
`_format_metadata_items`'s own docstring: whatever a strategy attaches, no
fixed schema), as "{label} {value}" pills. A strategy that actually
attaches `r_multiple`/`fee` metadata gets pills close to the mockup's
wording but not identical to it; hardcoding "R"/"Phí" as dedicated fields
would mean assuming every strategy tracks exactly those two numbers, which
nothing in the domain currently guarantees.

## Not yet wired into a screen

Nothing in `screens/` constructs `TradeLogVM` yet — Backtest keeps
rendering this table through `backtest_trade_logs_panel.py` today.
`preview.py` seeds six example trades matching the mockup's tab counts
(6 total, 4 long, 2 short, 2 wins, 4 losses) as real `TradeLogRow` instances
— the same dataclass `build_trade_log_rows()` produces from a run's actual
`Trade` list — not a fabricated dict shape.
