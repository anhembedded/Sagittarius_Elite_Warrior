import QtQuick
import QtQuick.Layouts

// One row of `PositionsTable.qml` — renders a pre-formatted dict from
// `positions_row.position_row_to_qml`. Sizes itself with the
// `ListView.view.width` attached property (`qml/DataTable/NOTES.md`
// explains why an `id` reference does not work once the `ListView` lives
// inside `DataTable.qml`, a different file from this delegate).
RowLayout {
    id: root
    objectName: "positionRow_" + (index + 1)
    spacing: 8
    height: 30

    property int symbolWidth: 110
    property int sideWidth: 70
    property int sizeWidth: 120
    property int priceWidth: 130
    property int leverageWidth: 70
    property int liquidationWidth: 130

    Text {
        objectName: "positionSymbol_" + (index + 1)
        Layout.preferredWidth: root.symbolWidth
        text: modelData.symbol
        textFormat: Text.PlainText
        color: Theme.textPrimary
        font.pixelSize: 12
    }

    Text {
        objectName: "positionSide_" + (index + 1)
        Layout.preferredWidth: root.sideWidth
        text: modelData.sideLabel
        textFormat: Text.PlainText
        color: modelData.sideIsLong ? Theme.success : Theme.danger
        font.pixelSize: 12
        font.bold: true
    }

    Text {
        objectName: "positionSize_" + (index + 1)
        Layout.preferredWidth: root.sizeWidth
        horizontalAlignment: Text.AlignRight
        text: modelData.sizeText
        textFormat: Text.PlainText
        color: Theme.textPrimary
        font.pixelSize: 12
    }

    Text {
        objectName: "positionEntry_" + (index + 1)
        Layout.preferredWidth: root.priceWidth
        horizontalAlignment: Text.AlignRight
        text: modelData.entryText
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 12
    }

    Text {
        objectName: "positionMark_" + (index + 1)
        Layout.preferredWidth: root.priceWidth
        horizontalAlignment: Text.AlignRight
        text: modelData.markText
        textFormat: Text.PlainText
        color: Theme.textPrimary
        font.pixelSize: 12
    }

    Text {
        objectName: "positionPnl_" + (index + 1)
        Layout.fillWidth: true
        horizontalAlignment: Text.AlignRight
        text: modelData.pnlText
        textFormat: Text.PlainText
        color: modelData.pnlColor
        font.pixelSize: 12
        font.bold: true
    }

    Text {
        objectName: "positionLeverage_" + (index + 1)
        Layout.preferredWidth: root.leverageWidth
        horizontalAlignment: Text.AlignRight
        text: modelData.leverageText
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 12
    }

    Text {
        objectName: "positionLiquidation_" + (index + 1)
        Layout.preferredWidth: root.liquidationWidth
        horizontalAlignment: Text.AlignRight
        text: modelData.liquidationText
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 12
    }
}
