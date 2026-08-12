import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// One row of the "Thông số Bot" modal (BOT-047) — picks its widget purely
// from `fieldData.kind` ("int"/"float"/"bool"/"string"), never from which
// strategy it belongs to. `currentValue` holds the user's in-progress edit;
// nothing is written back to Python until BotParamsDialog's "Lưu &
// Re-Backtest" collects every field's `currentValue` at once.
Item {
    id: root

    required property var fieldData

    //: Marks this item for BotParamsDialog's recursive collector — see its
    //: _collectFieldItems().
    readonly property bool isBotParamField: true
    readonly property string fieldName: fieldData.name
    property var currentValue: fieldData.value

    //: A stand-in for "no bound" — QML properties can't be `undefined` the
    //: way Python's `None` can, and int/DoubleValidator both require a real
    //: number for bottom/top.
    readonly property real _noLowerBound: -999999999
    readonly property real _noUpperBound: 999999999

    implicitHeight: column.implicitHeight
    implicitWidth: column.implicitWidth

    // Reached directly (not just through the `currentValue`/binding pair)
    // because a TextField's `text: ...` binding is broken the first time the
    // user types into it (standard QML TextInput behaviour, same as
    // txtBacktestCapital elsewhere in this screen) — "Khôi phục Mặc định"
    // has to work even after that, so it writes the loaded item's own
    // property imperatively instead of trusting the binding to still be
    // live.
    function resetToDefault() {
        currentValue = fieldData.default
        var item = fieldLoader.item
        if (!item) return
        if (fieldData.kind === "bool") {
            item.checked = fieldData.default
        } else if ("currentIndex" in item && "model" in item) {
            var idx = item.model.indexOf(fieldData.default)
            if (idx >= 0) item.currentIndex = idx
        } else {
            item.text = String(fieldData.default)
        }
    }

    ColumnLayout {
        id: column
        width: root.width
        spacing: 4

        Text {
            text: fieldData.label + (fieldData.suffix !== "" ? " (" + fieldData.suffix + ")" : "")
            color: Theme.textSecondary
            font.pixelSize: 10
        }

        Loader {
            id: fieldLoader
            Layout.fillWidth: true
            sourceComponent: {
                if (fieldData.kind === "int") return intFieldComponent
                if (fieldData.kind === "float") return floatFieldComponent
                if (fieldData.kind === "bool") return boolFieldComponent
                if (fieldData.options && fieldData.options.length > 0) return dropdownFieldComponent
                return textFieldComponent
            }
        }
    }

    Component {
        id: intFieldComponent
        TextField {
            objectName: "fldBotParam_" + root.fieldName
            implicitHeight: 32
            text: String(root.currentValue)
            color: Theme.textPrimary
            font.pixelSize: 11
            background: FieldBackground {}
            validator: IntValidator {
                bottom: fieldData.minval !== null && fieldData.minval !== undefined ? fieldData.minval : root._noLowerBound
                top: fieldData.maxval !== null && fieldData.maxval !== undefined ? fieldData.maxval : root._noUpperBound
            }
            onEditingFinished: root.currentValue = text
        }
    }

    Component {
        id: floatFieldComponent
        TextField {
            objectName: "fldBotParam_" + root.fieldName
            implicitHeight: 32
            text: String(root.currentValue)
            color: Theme.textPrimary
            font.pixelSize: 11
            background: FieldBackground {}
            validator: DoubleValidator {
                bottom: fieldData.minval !== null && fieldData.minval !== undefined ? fieldData.minval : root._noLowerBound
                top: fieldData.maxval !== null && fieldData.maxval !== undefined ? fieldData.maxval : root._noUpperBound
            }
            onEditingFinished: root.currentValue = text
        }
    }

    Component {
        id: boolFieldComponent
        StyledCheck {
            objectName: "fldBotParam_" + root.fieldName
            text: ""
            checked: root.currentValue === true
            onToggled: root.currentValue = checked
        }
    }

    Component {
        id: dropdownFieldComponent
        ComboBox {
            id: dropdown
            objectName: "fldBotParam_" + root.fieldName
            implicitHeight: 32
            model: fieldData.options
            background: FieldBackground {}
            contentItem: Text {
                leftPadding: 8
                text: dropdown.displayText
                color: Theme.textPrimary
                font.pixelSize: 11
                verticalAlignment: Text.AlignVCenter
            }

            property bool _initialized: false
            Component.onCompleted: {
                var idx = model.indexOf(root.currentValue)
                if (idx >= 0) currentIndex = idx
                _initialized = true
            }
            onActivated: (index) => {
                if (_initialized) root.currentValue = model[index]
            }
        }
    }

    Component {
        id: textFieldComponent
        TextField {
            objectName: "fldBotParam_" + root.fieldName
            implicitHeight: 32
            text: String(root.currentValue)
            color: Theme.textPrimary
            font.pixelSize: 11
            background: FieldBackground {}
            onEditingFinished: root.currentValue = text
        }
    }
}
