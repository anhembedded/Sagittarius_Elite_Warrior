import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../kit"
import "../DataTable"

// Layout and bindings only (EPIC-015 §3.2). Renders `DatabaseStatusVM`'s
// real production model (`DatabaseStatusTableModel`, filtered through the
// VM's own `DatabaseStatusFilterProxy`) — search and row actions are both
// wired now (EPIC-015 Phase 2, NOTES.md). Body for a `QmlOverlay`-style
// host, but this widget is table content rather than a modal — whichever
// screen embeds it owns its own chrome.
//
// Header is the shared `kit/PanelHeader` (retrofitted 2026-08-30, see
// `qml/kit/NOTES.md`) — not a hand-rolled accent bar + label anymore.
//
// Column headers + row-list + empty-state skeleton is `DataTable`
// (`BOT-124`) — the `PanelHeader`/search field above it and the per-row
// action buttons (in `DatabaseStatusRow.qml`) stay here (BOT-124 §5: what
// doesn't generalize).
ColumnLayout {
    id: root
    objectName: "databaseStatusBody"
    spacing: 10

    readonly property int symbolColumnWidth: 160
    readonly property int tfColumnWidth: 60
    readonly property int statusColumnWidth: 150
    readonly property int actionsColumnWidth: 230

    PanelHeader {
        Layout.fillWidth: true
        title: "Database Status"
        badgeText: (vm ? vm.rowCount : 0) + " shard" + ((vm && vm.rowCount === 1) ? "" : "s")

        TextField {
            id: searchField
            objectName: "txtDatabaseStatusSearch"
            width: 180
            implicitHeight: 26
            font.pixelSize: 11
            placeholderText: "Tìm symbol / khung thời gian…"
            color: Theme.textPrimary
            selectByMouse: true
            onTextEdited: if (vm) vm.setSearchText(text)
            background: Rectangle {
                color: Theme.bg
                border.width: 1
                border.color: searchField.activeFocus ? Theme.accent : Theme.stateNavBorder
                radius: 6
            }
        }
    }

    // Ports the old `_empty_label`'s exact message and trigger
    // (`model.rowCount() == 0`, the same filtered count `vm.rowCount`
    // reports here) — so an empty vault and a search with zero matches
    // both read the same as they did before this widget replaced the
    // QListView-based table.
    DataTable {
        Layout.fillWidth: true
        Layout.fillHeight: true
        listObjectName: "databaseStatusRows"
        emptyObjectName: "lblDatabaseStatusEmpty"
        headerLetterSpacing: 0.8
        rowSpacing: 2
        columns: [
            { key: "symbol", label: "SYMBOL", width: root.symbolColumnWidth },
            { key: "tf", label: "TF", width: root.tfColumnWidth },
            { key: "firstRecord", label: "FIRST RECORD", fillWidth: true },
            { key: "lastRecord", label: "LAST RECORD", fillWidth: true },
            { key: "status", label: "TOTAL STATUS", width: root.statusColumnWidth, align: "right" },
            { key: "actions", label: "ACTIONS", width: root.actionsColumnWidth, align: "right" },
        ]
        rowsModel: vm ? vm.rowsModel : null
        isEmpty: vm ? vm.rowCount === 0 : false
        emptyText: "Storage Vault trống. Hãy chọn Symbol & Timeframe và nhấn 'Sync' để tải dữ liệu."
        rowDelegate: Component {
            DatabaseStatusRow {
                width: ListView.view.width
                symbolWidth: root.symbolColumnWidth
                tfWidth: root.tfColumnWidth
                statusWidth: root.statusColumnWidth
                actionsWidth: root.actionsColumnWidth
            }
        }
    }
}
