import QtQuick
import QtQuick.Layouts

// One row of the K-line inspector table. Every field reads
// `modelData.<key>` — already-formatted display text from
// `kline_display_row_to_qml` (data_management/kline_inspector_table_model.py),
// not computed here. `KlineInspectorVM.rows` is a plain list of dicts, not
// a `QAbstractListModel`, so a delegate addresses fields through
// `modelData` (contrast `DatabaseStatusRow.qml`, whose model is a real
// `QAbstractListModel` with declared `roleNames()`).
//
// Monospace on every price cell — a column of prices only lines up if its
// digits are the same width (same reasoning `_KLineRowWidget` documents).
Item {
    id: root
    implicitHeight: 26

    property int timeWidth: 170
    property int priceWidth: 100
    property int volumeWidth: 110
    property int changeWidth: 90

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 8

        Text {
            Layout.preferredWidth: root.timeWidth
            text: modelData.formattedTime
            textFormat: Text.PlainText
            font.family: "monospace"
            color: Theme.textPrimary
            font.pixelSize: 11
        }
        Text {
            Layout.preferredWidth: root.priceWidth
            horizontalAlignment: Text.AlignRight
            text: modelData.openPrice
            textFormat: Text.PlainText
            font.family: "monospace"
            color: Theme.textPrimary
            font.pixelSize: 11
        }
        Text {
            Layout.preferredWidth: root.priceWidth
            horizontalAlignment: Text.AlignRight
            text: modelData.highPrice
            textFormat: Text.PlainText
            font.family: "monospace"
            color: Theme.textPrimary
            font.pixelSize: 11
        }
        Text {
            Layout.preferredWidth: root.priceWidth
            horizontalAlignment: Text.AlignRight
            text: modelData.lowPrice
            textFormat: Text.PlainText
            font.family: "monospace"
            color: Theme.textPrimary
            font.pixelSize: 11
        }
        Text {
            objectName: "klineClose_" + modelData.timestampMs
            Layout.preferredWidth: root.priceWidth
            horizontalAlignment: Text.AlignRight
            text: modelData.closePrice
            textFormat: Text.PlainText
            font.family: "monospace"
            font.bold: true
            color: modelData.isBullish ? Theme.success : Theme.danger
            font.pixelSize: 11
        }
        Text {
            Layout.preferredWidth: root.volumeWidth
            horizontalAlignment: Text.AlignRight
            text: modelData.volume
            textFormat: Text.PlainText
            font.family: "monospace"
            color: Theme.muted
            font.pixelSize: 11
        }
        Text {
            objectName: "klineChange_" + modelData.timestampMs
            Layout.preferredWidth: root.changeWidth
            horizontalAlignment: Text.AlignRight
            text: modelData.changePct
            textFormat: Text.PlainText
            font.family: "monospace"
            color: modelData.isBullish ? Theme.success : Theme.danger
            font.pixelSize: 11
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignRight
            text: modelData.trades
            textFormat: Text.PlainText
            font.family: "monospace"
            color: Theme.muted
            font.pixelSize: 11
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.border
    }
}
