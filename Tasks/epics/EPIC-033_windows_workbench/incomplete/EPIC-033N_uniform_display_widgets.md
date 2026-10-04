# EPIC-033N — Every table, list and read-out is built from one spec per kind

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "ko chỉ cần control thống nhất, mà các widget hiện thị cũng phải thống nhất, ví dụ mấy cái mảng thì phải thông nhất các properti" (not only the controls: the display widgets must be uniform too, e.g. the tables must share the same properties).
**Risk:** 🟡 — every data view changes how it sorts, aligns and formats
**Complexity:** M — 12 item views, every read-out form and every display formatter
**Epic:** [EPIC-033](../README.md)
**Depends on:** Engine W6, EPIC-033C

---

## 1. Context and problem
The 12 item views in `src` are configured by hand, one file each: selection behaviour is set on 8, edit triggers on 4, header resize modes by 26 separate `setSectionResizeMode` calls, numbers right-aligned in 8 places. The Watchlist gives Symbol ~880 px and squeezes the numbers. Values are formatted by per-screen helpers (`kline_inspector_table_model._format_price`, `trade_log_row._format_datetime`, `trade_log_row._format_compact_usd`, `amount_text.format_amount`, …), so one price prints differently on two screens. Read-outs (Available / Max buy / Total / Est. fee) are label pairs laid out per panel.

## 2. Acceptance criteria
- [ ] Every `QTableView`/`QTreeView`/`QListView` in `src` is built through the Engine's `configure_item_view()` with a `ColumnSpec` per column; no view sets selection, edit triggers, sorting, header resize or alternating rows itself (033B static ban).
- [ ] A column's kind alone decides its alignment (text left; quantity, price, percent, money right; timestamp and side fixed), width policy (content-sized; one stretch column, the last text column), sort role (the raw value, never the display string) and display text.
- [ ] Every displayed number, price, percent, money amount, duration and timestamp goes through the app's `ValueFormatter` implementation (precision per symbol from exchange filters, one timestamp format, one percent format); the per-screen helpers are deleted.
- [ ] Every label–value read-out is a `ReadoutForm`; values align to the same column and use the formatter.
- [ ] Empty data shows one empty state per view kind (placeholder text in the view, not a separate panel).
- [ ] 033B's conformance check finds no visible view whose properties differ from its spec.

## 3. Design
Declarative column specs as in Qt's own model/view practice and every trading terminal's grids (P5): the model exposes raw values in `Qt.UserRole` and display text through the formatter; the view never decides presentation per screen. Mechanism (spec, kinds, view configuration, read-out form, formatter port) is Engine W6; policy (which kinds a table has, precision per symbol) is the app's (TASK-043's split: the Engine owns mechanism, the app owns policy).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| Every module table model and view (12 files) | Declare `ColumnSpec`s; drop per-view configuration |
| `src/support/formatting/` (new) | The app's `ValueFormatter`, precision from exchange filters |
| Per-screen formatters listed in §1 | Deleted, callers use the formatter |
| Read-out panels (order entry, account summary, Dev Board session/strategy) | `ReadoutForm` |

## 5. Testing
Unit: formatter per kind with boundary values (zero, negative, sub-tick, very large); each table's spec. Integration: conformance suite's item-view check; sorting a price column sorts numerically.

## Implementation notes (written when done)
Not started.
