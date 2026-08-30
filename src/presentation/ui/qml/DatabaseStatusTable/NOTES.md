# DatabaseStatusTable

QML port of the Data Management screen's per-symbol/interval status table.
User decision 2026-08-29: build the frame first, real features later
("dựng khung trước, đủ tính năng sau"). `EPIC-015` Phase 2 (2026-08-30)
finished the rest: search, row actions, and the idle/busy toggle are all
real and wired into the screen now — this file used to describe a
structural-pass-only widget; that era is over, see the section below.

## Reuses the real production model, not a copy

`DatabaseStatusVM` wraps `data_management/database_status_table_model.py`'s
`DatabaseStatusTableModel` directly — that model's own docstring already
says it "exposes named roles so QML delegates address fields by role
name," which is exactly what `DatabaseStatusTable.qml`'s `ListView` binds
to (through the VM's own filter proxy, see below). A host constructs this
VM with the same model instance `DataManagementViewModel.status_model`
already owns; nothing here holds a second copy of a row's data.

## Search — the VM owns the filter proxy, not the host

`DatabaseStatusVM` builds its own `DatabaseStatusFilterProxy` (same file as
the table model) around the raw model it is given, and `rowsModel` now
returns that proxy — a host never sees the raw model. `setSearchText(text)`
(a `Slot(str)`) forwards to it. `DatabaseStatusTable.qml`'s header carries
a `TextField` (`txtDatabaseStatusSearch`) styled per `qml-rule.md` §3 from
`SymbolPicker.qml`'s search field, calling `vm.setSearchText()` on
`onTextEdited`. This intentionally does **not** reuse
`DataManagementViewModel`'s own `_status_proxy`/`searchText`/`statusModel`
— those were removed from the screen ViewModel once nothing else read them
(the old `QListView` path was their only caller); the widget is
self-contained and does its own filtering from the one raw model, per
`qml-rule.md` §1.3's "widget owns its own concerns" default.

## Row actions — wired at the composition root, not in `.qml`

The buttons already rendered before this pass, including `Gaps` only
appearing on an unhealthy row (`set_action_visible(GAPS, not is_healthy)`
ported faithfully), and already emitted `vm.requestAction(action, symbol,
interval)` on click — that part needed no new `.qml`. What Phase 2 added is
the listener: `DatabaseStatusPanel`
(`screens/data_management/data_management_widgets/database_status_panel.py`)
connects `DatabaseStatusVM.rowActionRequested` to the real
`DataManagementViewModel.requestInspectKlines`/`requestInspectGaps`/
`requestSyncRow`/`requestClearRow` — the same four calls the old
`_status_row.py`'s `_on_action` used to make before it was deleted.

## Idle/busy toggle

`DatabaseStatusVM.actionsEnabled` (`Property(bool)`, `Slot(bool)
setActionsEnabled`) mirrors `_StatusRowWidget.apply_ui_mode(idle)`'s exact
rule — while not idle, all four of a row's action buttons are disabled.
`DatabaseStatusRow.qml`'s four `Button`s each bind `enabled:
vm.actionsEnabled`. `DataManagementView._sync_ui_mode()` calls
`DatabaseStatusPanel.set_actions_enabled(idle)` on every `uiMode` change,
the same trigger the old widget used.

## Wired into a screen: `DatabaseStatusPanel`

`screens/data_management/data_management_widgets/database_status_panel.py`
is the composition root — a `kit.Panel` (not a `QmlOverlay`: this table is
embedded inline in the screen's own layout, not a modal, so `Overlay`
chrome would be wrong here — see `qml-rule.md` §0) holding a bare
`QQuickWidget`. It seeds `Theme`/`ensure_qml_style()` the same way
`QmlOverlay.__init__` (`qml/host.py`) does for a modal host, since that
seeding is per-`QQuickWidget`, not something the app bootstrapper already
covers for an embedded one. `DataManagementView` constructs it in
`set_view_model()` (lazily, like `_kline_inspector`/`_gap_inspector`/
`_timeframe_picker` — `_build_ui()` runs before a view model exists to
build it from) and inserts it where the old `QListView`-based table card
used to live. `_status_row.py`, `_status_columns.py`, and
`data_management_widgets/row_delegate.py` are deleted — nothing else
referenced them.

`preview.py` still seeds the same two example rows via the model's own
`upsert_row()`; `.\scripts\preview-qml.ps1 DatabaseStatusTable` reviews the
widget standalone, `.\scripts\preview-qml.ps1 data_management` reviews it
embedded in the real screen. The Trade Log table remains deferred (larger
scope, see conversation 2026-08-29).
