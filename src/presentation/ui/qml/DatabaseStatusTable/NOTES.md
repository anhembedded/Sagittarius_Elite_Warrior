# DatabaseStatusTable

QML port of the Data Management screen's per-symbol/interval status table.
User decision 2026-08-29: build the frame first, real features later
("dựng khung trước, đủ tính năng sau") — this is a structural pass, and it
is scoped narrower than the mockup on purpose.

## Reuses the real production model, not a copy

`DatabaseStatusVM` wraps `data_management/database_status_table_model.py`'s
`DatabaseStatusTableModel` directly — that model's own docstring already
says it "exposes named roles so QML delegates address fields by role
name," which is exactly what `DatabaseStatusTable.qml`'s `ListView` binds
to. A real host constructs this VM with the same model instance
`DataManagementViewModel.status_model` already owns; nothing here holds a
second copy of a row's data.

## What the mockup has that this pass does not build yet

- **Search** ("Search symbol / timeframe"). `DatabaseStatusFilterProxy`
  (same file as the table model) already implements this exact search —
  substring match against symbol or interval — so wiring it later is
  connecting an existing, tested class, not writing new filtering logic.
  Not done here because the search box itself is not rendered yet: an
  unwired text field that visibly does nothing was judged worse than
  waiting to add both together.
- **Row actions** (KLines/Gaps/Sync/Clear). The buttons render — including
  `Gaps` only appearing on an unhealthy row, the real
  `set_action_visible(GAPS, not is_healthy)` rule ported faithfully — and
  clicking one emits `vm.requestAction(action, symbol, interval)`. That
  signal has no listener yet; a future host connects it to
  `DataManagementViewModel.requestInspectKlines`/`requestSyncRow`/
  `requestClearRow`/`requestInspectGaps`, the same four calls
  `_status_row.py`'s `_on_action` already makes.

## Not yet wired into a screen

Nothing in `screens/` constructs `DatabaseStatusVM` yet — Data Management
keeps rendering this table through `_status_row.py`'s `QListView` +
`DataRow` today. `preview.py` seeds the same two example rows the mockup
shows, via the model's own `upsert_row()` (not a second, fabricated data
shape), so this can be reviewed with `.\scripts\uml_preview.ps1
src/presentation/ui/qml/DatabaseStatusTable` before either wiring or the
Trade Log table (deferred — larger scope, see conversation 2026-08-29) is
tackled.
