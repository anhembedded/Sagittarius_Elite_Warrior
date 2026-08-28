import QtQuick
import QtQuick.Controls

// Layout and bindings only. Every rule — including which row is selected —
// lives in `timezone_picker_vm.py`, where the gate can see it (EPIC-015 §3.2).
// No colour literal here: `Theme` is the only source (EPIC-015 §3.3).
ScrollView {
    id: root
    clip: true

    Column {
        objectName: "tzList"
        width: root.width
        spacing: 6

        Repeater {
            model: vm.rows

            Rectangle {
                objectName: "tzItem_" + modelData.id
                width: parent.width
                height: 40
                radius: 4
                color: modelData.selected ? Theme.stateActiveTint : Theme.bgCardHeader
                border.width: 1
                border.color: modelData.selected ? Theme.accent : Theme.stateNavBorder

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    text: modelData.label
                    color: modelData.selected ? Theme.accent : Theme.textPrimary
                    font.bold: modelData.selected
                    font.pixelSize: 12
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vm.choose(modelData.id)
                }
            }
        }
    }
}
