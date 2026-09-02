import QtQuick
import QtQuick.Layouts
import "../DataTable"

// Layout and bindings only (EPIC-015 §3.2), renders `PositionsVM.rows`.
// Header + row-list + empty-state skeleton is `DataTable` (`BOT-124`) —
// only the column widths/labels and the row delegate stay here, same
// split `TradeLogTable.qml` uses.
ColumnLayout {
    id: root
    objectName: "positionsTableBody"
    spacing: 10

    readonly property int symbolColumnWidth: 110
    readonly property int sideColumnWidth: 70
    readonly property int sizeColumnWidth: 120
    readonly property int priceColumnWidth: 130
    readonly property int leverageColumnWidth: 70
    readonly property int liquidationColumnWidth: 130

    DataTable {
        Layout.fillWidth: true
        Layout.fillHeight: true
        listObjectName: "positionsRows"
        emptyObjectName: "lblPositionsEmpty"
        headerLetterSpacing: 0.5
        reuseItems: true
        columns: [
            { key: "symbol", label: "SYMBOL", width: root.symbolColumnWidth },
            { key: "side", label: "CHIỀU", width: root.sideColumnWidth },
            { key: "size", label: "KHỐI LƯỢNG", width: root.sizeColumnWidth, align: "right" },
            { key: "entry", label: "GIÁ VÀO", width: root.priceColumnWidth, align: "right" },
            { key: "mark", label: "GIÁ HIỆN TẠI", width: root.priceColumnWidth, align: "right" },
            { key: "pnl", label: "PNL CHƯA THỰC HIỆN", fillWidth: true, align: "right" },
            { key: "leverage", label: "ĐÒN BẨY", width: root.leverageColumnWidth, align: "right" },
            { key: "liquidation", label: "GIÁ THANH LÝ", width: root.liquidationColumnWidth, align: "right" },
        ]
        rowsModel: vm.rows
        isEmpty: vm.rows.length === 0
        emptyText: "Không có vị thế đang mở"
        rowDelegate: Component {
            PositionRow {
                width: ListView.view.width
                symbolWidth: root.symbolColumnWidth
                sideWidth: root.sideColumnWidth
                sizeWidth: root.sizeColumnWidth
                priceWidth: root.priceColumnWidth
                leverageWidth: root.leverageColumnWidth
                liquidationWidth: root.liquidationColumnWidth
            }
        }
    }
}
