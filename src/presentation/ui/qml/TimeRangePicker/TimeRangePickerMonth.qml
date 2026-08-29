import QtQuick
import QtQuick.Layouts

// Reusable one-month calendar grid. Pure layout — every cell's colour comes
// from `edge`/`inside`/`outside` flags TimeRangePickerVM already computed
// (EPIC-015 §1.2: no lookup/branching here beyond one ternary per binding).
ColumnLayout {
    id: root
    property string monthLabel: ""
    property var days: []
    property var weekdayLabels: []
    signal dayClicked(string iso)

    spacing: 8

    Text {
        Layout.fillWidth: true
        horizontalAlignment: Text.AlignHCenter
        text: root.monthLabel
        textFormat: Text.PlainText
        color: Theme.textPrimary
        font.bold: true
        font.pixelSize: 12
    }

    GridLayout {
        columns: 7
        rowSpacing: 3
        columnSpacing: 0

        Repeater {
            model: root.weekdayLabels
            Text {
                Layout.preferredWidth: 32
                horizontalAlignment: Text.AlignHCenter
                text: modelData
                textFormat: Text.PlainText
                color: Theme.muted
                font.pixelSize: 10
            }
        }

        Repeater {
            model: root.days
            Rectangle {
                objectName: "timeRangeDay_" + modelData.iso
                Layout.preferredWidth: 32
                Layout.preferredHeight: 26
                radius: modelData.inside ? 0 : 6
                color: modelData.edge
                    ? Theme.accent
                    : modelData.inside
                        ? Theme.stateActiveTint
                        : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: modelData.day
                    textFormat: Text.PlainText
                    color: modelData.outside
                        ? Theme.border
                        : modelData.edge
                            ? Theme.bg
                            : Theme.textPrimary
                    font.pixelSize: 12
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: !modelData.outside
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.dayClicked(modelData.iso)
                }
            }
        }
    }
}
