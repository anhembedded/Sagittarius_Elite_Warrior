import QtQuick
import QtQuick.Layouts

// Compact pill row — reads only `vm.pinnedRows`/`vm.currentCode`. Opening
// the full picker is a screen-composition decision, not this widget's: the
// "…" button only emits `moreRequested()`, and the host decides what
// opening means (same reasoning `ChartToolbar._open_picker()` documents,
// moved out of the widget now that pinning makes the picker's state
// something this row must also reflect, not just trigger).
RowLayout {
    id: root
    objectName: "timeframeToolbar"
    spacing: 4

    signal moreRequested()

    Repeater {
        model: vm.pinnedRows
        Rectangle {
            objectName: "timeframePill_" + modelData.code
            implicitWidth: Math.max(pillLabel.implicitWidth + 16, 34)
            implicitHeight: 22
            radius: 4
            color: modelData.current ? Theme.stateActiveTint : Theme.stateIdleBg
            border.width: 1
            border.color: modelData.current ? Theme.accent : Theme.stateNavBorder

            Text {
                id: pillLabel
                anchors.centerIn: parent
                text: modelData.code
                textFormat: Text.PlainText
                color: modelData.current ? Theme.accent : Theme.muted
                font.pixelSize: 11
                font.bold: modelData.current
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: vm.choose(modelData.code)
            }
        }
    }

    Rectangle {
        objectName: "btnTimeframeMore"
        implicitWidth: 34
        implicitHeight: 22
        radius: 4
        color: Theme.stateIdleBg
        border.width: 1
        border.color: Theme.stateNavBorder

        Text {
            anchors.centerIn: parent
            text: "…"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 11
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.moreRequested()
        }
    }
}
