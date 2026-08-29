import QtQuick
import QtQuick.Layouts

// Layout and bindings only (EPIC-015 §3.2). Renders `TradeLogVM`'s rows —
// structural pass only: no search box, no export, no pagination (replaced
// by ListView virtualization), no row-expand/column-sort yet (NOTES.md).
// Column headers repeat `backtest_trade_logs_panel.py`'s `_HEADERS` text
// verbatim — same table, not a redesign of its wording.
ColumnLayout {
    id: root
    objectName: "tradeLogBody"
    spacing: 10

    readonly property int timeColumnWidth: 190
    readonly property int sideColumnWidth: 90
    readonly property int priceColumnWidth: 190
    readonly property int sizeColumnWidth: 130

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

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        Text {
            Layout.preferredWidth: root.timeColumnWidth
            text: "STT / THỜI GIAN"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.5
        }
        Text {
            Layout.preferredWidth: root.sideColumnWidth
            text: "LOẠI"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.5
        }
        Text {
            Layout.preferredWidth: root.priceColumnWidth
            text: "GIÁ VÀO  ➔  GIÁ THOÁT"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.5
        }
        Text {
            Layout.preferredWidth: root.sizeColumnWidth
            horizontalAlignment: Text.AlignRight
            text: "QUY MÔ / KHỐI LƯỢNG"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.5
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignRight
            text: "LÃI / LỖ RÒNG"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.5
        }
        Text {
            Layout.preferredWidth: 70
            horizontalAlignment: Text.AlignRight
            text: "RETURN"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.5
        }
    }

    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

    ListView {
        id: rowsView
        objectName: "tradeLogRows"
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        reuseItems: true
        model: vm.rows
        delegate: TradeLogRow {
            width: rowsView.width
            timeWidth: root.timeColumnWidth
            sideWidth: root.sideColumnWidth
            priceWidth: root.priceColumnWidth
            sizeWidth: root.sizeColumnWidth
        }
    }

    Text {
        objectName: "lblTradeLogEmpty"
        Layout.fillWidth: true
        Layout.topMargin: 12
        visible: vm.rows.length === 0
        horizontalAlignment: Text.AlignHCenter
        text: "Chưa có dữ liệu lệnh giao dịch"
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 11
    }
}
