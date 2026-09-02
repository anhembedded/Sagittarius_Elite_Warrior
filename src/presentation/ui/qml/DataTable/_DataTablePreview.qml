import QtQuick
import QtQuick.Layouts

// Standalone demo of `DataTable` in isolation — a trivial two-column row
// delegate, not a real table's row shape, since `DataTable` has no opinion
// on what a row looks like (BOT-124 §5). The three real callers each keep
// their own `preview.py` showing their real row delegate; this file is
// only for `DataTable`'s own header/list/empty skeleton.
Rectangle {
    width: 640
    height: 360
    color: Theme.bg

    DataTable {
        anchors.fill: parent
        anchors.margins: 16
        headerLetterSpacing: 0.5
        listObjectName: "dataTablePreviewRows"
        emptyObjectName: "dataTablePreviewEmpty"
        columns: [
            { key: "symbol", label: "SYMBOL", width: 140 },
            { key: "side", label: "SIDE", width: 90, align: "right" },
            { key: "price", label: "PRICE", fillWidth: true, align: "right" },
        ]
        rowsModel: [
            { symbol: "BTCUSDT", side: "LONG", price: "64,105.35" },
            { symbol: "ETHUSDT", side: "SHORT", price: "3,412.10" },
        ]
        isEmpty: false
        emptyText: "No rows"
        rowDelegate: Component {
            RowLayout {
                width: ListView.view.width
                height: 28
                spacing: 8

                Text {
                    Layout.preferredWidth: 140
                    text: modelData.symbol
                    textFormat: Text.PlainText
                    color: Theme.textPrimary
                    font.pixelSize: 11
                }
                Text {
                    Layout.preferredWidth: 90
                    horizontalAlignment: Text.AlignRight
                    text: modelData.side
                    textFormat: Text.PlainText
                    color: Theme.textPrimary
                    font.pixelSize: 11
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignRight
                    text: modelData.price
                    textFormat: Text.PlainText
                    color: Theme.textPrimary
                    font.pixelSize: 11
                }
            }
        }
    }
}
