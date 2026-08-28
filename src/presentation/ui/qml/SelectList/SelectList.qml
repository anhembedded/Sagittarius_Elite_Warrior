import QtQuick
import QtQuick.Controls

// Layout and bindings only (EPIC-015 §3.2). Shared by every "pick one from a
// list" and "read-only bullet list" modal — `vm.selectable` (set at
// construction, not per-row) is the only thing distinguishing the two.
//
// One `Item` per Repeater index, holding both shapes as ITS children. A
// Repeater accepts exactly one delegate: two Items placed directly as its
// immediate children silently collapse to only the last one being
// instantiated (measured — the "selectItem_" cards never rendered until
// this was wrapped). That is a real Qt Quick gotcha, not a hypothetical one.
ScrollView {
    id: root
    clip: true

    Column {
        objectName: "selectListRows"
        width: root.width
        spacing: 8

        Repeater {
            model: vm.rows

            Item {
                width: parent.width
                height: card.visible ? card.height : bullet.height

                Rectangle {
                    id: card
                    objectName: "selectItem_" + modelData.id
                    width: parent.width
                    height: modelData.subtitle ? 48 : 40
                    radius: 4
                    visible: vm.selectable
                    color: modelData.selected ? Theme.stateActiveTint : Theme.bgCardHeader
                    border.width: 1
                    border.color: modelData.selected ? Theme.accent : Theme.stateNavBorder

                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        spacing: 2

                        Text {
                            text: modelData.label
                            color: modelData.selected ? Theme.accent : Theme.textPrimary
                            font.bold: modelData.selected
                            font.pixelSize: 12
                        }
                        Text {
                            visible: modelData.subtitle !== ""
                            text: modelData.subtitle
                            color: Theme.muted
                            font.pixelSize: 10
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: vm.choose(modelData.id)
                    }
                }

                // Read-only shape: a bullet row instead of a selectable
                // card. Same Repeater/model, so both shapes stay one
                // component.
                Row {
                    id: bullet
                    objectName: "bulletItem_" + modelData.id
                    width: parent.width
                    visible: !vm.selectable
                    spacing: 10

                    Text {
                        text: "•"
                        color: Theme.muted
                        font.bold: true
                        font.pixelSize: 13
                    }
                    Text {
                        width: parent.width - 24
                        wrapMode: Text.WordWrap
                        text: modelData.label
                        color: Theme.textPrimary
                        font.pixelSize: 11
                    }
                }
            }
        }
    }
}
