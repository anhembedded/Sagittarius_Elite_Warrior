import QtQuick
import QtQuick.Layouts

// One row of `OpenOrdersTable.qml` — renders a pre-formatted dict from
// `open_order_row.open_order_row_to_qml`.
RowLayout {
    id: root
    objectName: "openOrderRow_" + (index + 1)
    spacing: 8
    height: 30

    property int timeWidth: 150
    property int symbolWidth: 110
    property int sideWidth: 70
    property int typeWidth: 130
    property int quantityWidth: 120
    property int priceWidth: 130

    Text {
        objectName: "openOrderTime_" + (index + 1)
        Layout.preferredWidth: root.timeWidth
        text: modelData.orderTimeText
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 12
    }

    Text {
        objectName: "openOrderSymbol_" + (index + 1)
        Layout.preferredWidth: root.symbolWidth
        text: modelData.symbol
        textFormat: Text.PlainText
        color: Theme.textPrimary
        font.pixelSize: 12
    }

    Text {
        objectName: "openOrderSide_" + (index + 1)
        Layout.preferredWidth: root.sideWidth
        text: modelData.sideLabel
        textFormat: Text.PlainText
        color: modelData.sideIsBuy ? Theme.success : Theme.danger
        font.pixelSize: 12
        font.bold: true
    }

    Text {
        objectName: "openOrderType_" + (index + 1)
        Layout.preferredWidth: root.typeWidth
        text: modelData.orderTypeText
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 12
    }

    Text {
        objectName: "openOrderQuantity_" + (index + 1)
        Layout.preferredWidth: root.quantityWidth
        horizontalAlignment: Text.AlignRight
        text: modelData.quantityText
        textFormat: Text.PlainText
        color: Theme.textPrimary
        font.pixelSize: 12
    }

    Text {
        objectName: "openOrderPrice_" + (index + 1)
        Layout.preferredWidth: root.priceWidth
        horizontalAlignment: Text.AlignRight
        text: modelData.priceText
        textFormat: Text.PlainText
        color: Theme.textPrimary
        font.pixelSize: 12
    }

    Text {
        objectName: "openOrderStatus_" + (index + 1)
        Layout.fillWidth: true
        horizontalAlignment: Text.AlignRight
        text: modelData.statusText
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 12
    }
}
