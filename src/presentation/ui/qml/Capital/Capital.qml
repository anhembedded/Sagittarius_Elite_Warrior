import QtQuick
import QtQuick.Controls

// Layout and bindings only (EPIC-015 §3.2). Note what is NOT here: no
// `_sync_validation`, no wiring between the field and the button's enabled
// state. Those are three declarations below, and they are the whole reason
// BUG-064 cannot recur in this shape.
Column {
    id: root
    spacing: 8

    Row {
        spacing: 8
        width: root.width

        TextField {
            objectName: "txtBacktestCapital"
            width: root.width - currency.width - 8
            text: vm.text
            onTextEdited: vm.text = text
            validator: DoubleValidator { bottom: 0; decimals: 8 }
            color: Theme.textPrimary
            background: Rectangle {
                color: Theme.bgCardHeader
                border.color: Theme.stateNavBorder
                border.width: 1
                radius: 4
            }
        }

        ComboBox {
            id: currency
            objectName: "cboBacktestCurrency"
            width: 90
            model: vm.currencies
            onActivated: vm.currency = currentText
            Component.onCompleted: currentIndex = model.indexOf(vm.currency)
        }
    }

    Text {
        objectName: "txtCapitalValidationMessage"
        width: root.width
        wrapMode: Text.WordWrap
        text: vm.validationMessage
        visible: vm.validationMessage !== ""
        color: Theme.danger
        font.pixelSize: 10
    }
}
