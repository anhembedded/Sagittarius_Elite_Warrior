import QtQuick
import QtQuick.Layouts

// Shared header + row-list + empty-state skeleton for every `qml/` table
// widget (`BOT-124`) — extracted from three near-identical copies
// (`TradeLogTable`, `KlineInspectorTable`, `DatabaseStatusTable`), each of
// which repeated the same root `ColumnLayout` -> header `RowLayout` ->
// divider `Rectangle` -> `ListView` -> empty `Text` skeleton, differing
// only in column widths/labels, model, row delegate, and empty-state copy
// (qml-rule.md §0.2; see this widget's own NOTES.md for the extraction).
//
// Deliberately does NOT own anything specific to one table: no filter tabs
// (`TradeLogTable`), no subtitle line (`KlineInspectorTable`), no search
// field or row actions (`DatabaseStatusTable`) — those stay in each
// caller's own `.qml` file, composed alongside `DataTable` rather than
// folded into it (BOT-124 §5). `DataTable` owns only the frame every table
// shares.
//
// Column widths stay a Single Source of Truth per column
// (ui-presentation-rule.md): each column descriptor's `width` is read by
// this component's header `Repeater`, and independently by whatever
// `rowDelegate` the caller supplies — the caller defines its own
// `readonly property int xColumnWidth` and passes the SAME value into
// both the matching `columns` entry and its row delegate's own width
// property, exactly as each of the three original tables already did for
// their own header/row pair.
ColumnLayout {
    id: root
    spacing: 10

    //: Header column descriptors, left to right. Each entry:
    //: `{ key: string (optional, used only to build a header-cell
    //:   objectName), label: string, width: int (omit for a fillWidth
    //:   column), fillWidth: bool (default false),
    //:   align: "left"|"right" (default "left") }`.
    //: DataTable never reads row data itself — `key` exists purely so a
    //: header cell can be found by name in a test.
    property var columns: []

    //: Passed straight through to the internal `ListView.model` — a plain
    //: list (`TradeLogVM`/`KlineInspectorVM` style) or a real
    //: `QAbstractListModel` (`DatabaseStatusTableModel` style) both work
    //: unchanged, exactly as the three original tables relied on.
    property var rowsModel: null

    //: The row `Component` the internal `ListView` instantiates. Defined
    //: in the CALLER's own `.qml` file (never here — `DataTable` stays
    //: ignorant of what a row looks like), so it closes over that file's
    //: own column-width properties. A row delegate sizes itself with the
    //: `ListView.view.width` attached property rather than an `id`
    //: reference into this file — the attachment happens at
    //: instantiation time, so it resolves correctly regardless of which
    //: `.qml` file the `Component` body is written in.
    property Component rowDelegate: null

    //: Whether to show the empty-state message. A plain bool, not derived
    //: here, because "empty" means something different per caller
    //: (`vm.rows.length === 0` vs. a null-guarded `vm.rowCount === 0`).
    property bool isEmpty: false
    property string emptyText: ""

    //: Every original table set these explicitly (or relied on Qt's own
    //: `ListView` default), so callers keep setting them explicitly here
    //: too, rather than a new caller silently inheriting a default it
    //: never chose.
    property bool reuseItems: false
    property real rowSpacing: 0

    //: Table-wide, not per-column — all three original tables used one
    //: `letterSpacing` value across their whole header row, never a
    //: per-column one.
    property real headerLetterSpacing: 0

    //: `objectName` for the internal `ListView`/empty `Text` — kept
    //: settable so a migrated table preserves its own exact
    //: pre-extraction name (nothing currently asserts on either, but a
    //: silent rename is still an avoidable behavior change).
    property string listObjectName: "dataTableRows"
    property string emptyObjectName: "dataTableEmpty"

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        Repeater {
            model: root.columns
            delegate: Text {
                objectName: "dataTableHeaderCell_" + (modelData.key !== undefined ? modelData.key : index)
                Layout.preferredWidth: modelData.width !== undefined ? modelData.width : -1
                Layout.fillWidth: !!modelData.fillWidth
                horizontalAlignment: modelData.align === "right" ? Text.AlignRight : Text.AlignLeft
                text: modelData.label
                textFormat: Text.PlainText
                color: Theme.muted
                font.pixelSize: 10
                font.letterSpacing: root.headerLetterSpacing
            }
        }
    }

    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

    ListView {
        id: rowsView
        objectName: root.listObjectName
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        reuseItems: root.reuseItems
        spacing: root.rowSpacing
        model: root.rowsModel
        delegate: root.rowDelegate
    }

    Text {
        objectName: root.emptyObjectName
        Layout.fillWidth: true
        Layout.topMargin: 12
        visible: root.isEmpty
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: root.emptyText
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 11
    }
}
