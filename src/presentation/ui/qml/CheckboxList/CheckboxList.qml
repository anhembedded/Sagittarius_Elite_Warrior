import QtQuick
import QtQuick.Controls

// Layout only. `locked` disables the row rather than hiding it — a locked
// row still says what it is, which is what the widget version's
// `checkbox.setEnabled(not locked)` did.
Column {
    id: root
    objectName: "checkboxListRows"
    width: parent.width
    spacing: 8

    Repeater {
        model: vm.rows

        Row {
            id: rowItem
            objectName: "checkboxRow_" + modelData.key
            width: root.width
            spacing: 10

            ToolTip.text: modelData.tooltip
            ToolTip.visible: modelData.tooltip !== "" && hoverHandler.hovered
            ToolTip.delay: 400
            HoverHandler { id: hoverHandler }

            CheckBox {
                objectName: "chk_" + modelData.key
                checked: modelData.checked
                enabled: !modelData.locked
                onToggled: vm.toggle(modelData.key, checked)
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.label
                color: Theme.textPrimary
                font.pixelSize: 12
            }
        }
    }
}
