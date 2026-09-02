import QtQuick
import QtQuick.Layouts
import "../DataTable"

// Layout and bindings only (EPIC-015 §3.2). Renders `TradeLogVM`'s rows —
// structural pass only: no search box, no export, no pagination (replaced
// by ListView virtualization), no row-expand/column-sort yet (NOTES.md).
// Column headers repeat `backtest_trade_logs_panel.py`'s `_HEADERS` text
// verbatim — same table, not a redesign of its wording.
//
// Header + row-list + empty-state skeleton is `DataTable` (`BOT-124`) —
// only the filter-tab row above it, the column widths/labels, and the row
// delegate stay here (BOT-124 §5: what doesn't generalize).
ColumnLayout {
    id: root
    objectName: "tradeLogBody"
    spacing: 10

    readonly property int timeColumnWidth: 190
    readonly property int sideColumnWidth: 90
    readonly property int priceColumnWidth: 190
    readonly property int sizeColumnWidth: 130
    //: `TradeLogRow.qml:112` already hardcodes this same `70` rather than
    //: reading a shared property (pre-existing, unrelated to this
    //: extraction) — kept as a literal here too, to match it exactly.
    readonly property int returnColumnWidth: 70

    Row {
        objectName: "tradeLogFilterTabs"
        Layout.fillWidth: true
        spacing: 4

        Repeater {
            model: vm.filterTabs
            Rectangle {
                objectName: "tabTradeLogFilter_" + modelData.id
                implicitWidth: tabLabel.implicitWidth + 20
                implicitHeight: 26
                radius: 6
                color: modelData.selected ? Theme.stateHoverBg : "transparent"
                border.width: 1
                border.color: modelData.selected ? Theme.stateNavBorder : "transparent"

                Text {
                    id: tabLabel
                    anchors.centerIn: parent
                    text: modelData.label + " · " + modelData.count
                    textFormat: Text.PlainText
                    color: modelData.selected ? Theme.textPrimary : Theme.muted
                    font.pixelSize: 11
                    font.bold: modelData.selected
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vm.chooseFilter(modelData.id)
                }
            }
        }
    }

    DataTable {
        Layout.fillWidth: true
        Layout.fillHeight: true
        listObjectName: "tradeLogRows"
        emptyObjectName: "lblTradeLogEmpty"
        headerLetterSpacing: 0.5
        reuseItems: true
        columns: [
            { key: "time", label: "STT / THỜI GIAN", width: root.timeColumnWidth },
            { key: "side", label: "LOẠI", width: root.sideColumnWidth },
            { key: "price", label: "GIÁ VÀO  ➔  GIÁ THOÁT", width: root.priceColumnWidth },
            { key: "size", label: "QUY MÔ / KHỐI LƯỢNG", width: root.sizeColumnWidth, align: "right" },
            { key: "pnl", label: "LÃI / LỖ RÒNG", fillWidth: true, align: "right" },
            { key: "return", label: "RETURN", width: root.returnColumnWidth, align: "right" },
        ]
        rowsModel: vm.rows
        isEmpty: vm.rows.length === 0
        emptyText: "Chưa có dữ liệu lệnh giao dịch"
        rowDelegate: Component {
            TradeLogRow {
                width: ListView.view.width
                timeWidth: root.timeColumnWidth
                sideWidth: root.sideColumnWidth
                priceWidth: root.priceColumnWidth
                sizeWidth: root.sizeColumnWidth
            }
        }
    }
}
