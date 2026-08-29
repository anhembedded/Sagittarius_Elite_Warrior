import QtQuick
import QtQuick.Layouts

// One stat card: title, value (+ optional suffix), and up to 2 badge
// pills — a verdict badge (colour-toned, e.g. "Rất kém") and/or an info
// badge (neutral, e.g. "≈ 34 ngày"). Every field is `modelData.<key>`
// from `MetricsDetailVM`'s row dicts — this delegate does no lookup or
// threshold logic of its own (see metrics_detail_vm.py for that).
Rectangle {
    id: root
    implicitHeight: content.implicitHeight + 24
    radius: 8
    color: Theme.bgCard
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 12
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Text {
                Layout.fillWidth: true
                text: modelData.title
                textFormat: Text.PlainText
                color: Theme.muted
                font.pixelSize: 10
                font.letterSpacing: 0.5
            }
            Rectangle {
                visible: modelData.badgeText !== ""
                radius: 4
                color: "transparent"
                border.width: 1
                border.color: modelData.badgeTone === "NEGATIVE" ? Theme.danger : Theme.stateNavBorder
                implicitWidth: badgeLabel.implicitWidth + 12
                implicitHeight: 18
                Text {
                    id: badgeLabel
                    anchors.centerIn: parent
                    text: modelData.badgeText
                    textFormat: Text.PlainText
                    color: modelData.badgeTone === "NEGATIVE" ? Theme.danger : Theme.textPrimary
                    font.pixelSize: 9
                }
            }
            Rectangle {
                visible: modelData.infoBadge !== ""
                radius: 4
                color: Theme.stateIdleBg
                border.width: 1
                border.color: Theme.stateNavBorder
                implicitWidth: infoLabel.implicitWidth + 12
                implicitHeight: 18
                Text {
                    id: infoLabel
                    anchors.centerIn: parent
                    text: modelData.infoBadge
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 9
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 4
            Text {
                text: modelData.value
                textFormat: Text.PlainText
                color: modelData.tone === "POSITIVE"
                    ? Theme.success
                    : modelData.tone === "NEGATIVE"
                        ? Theme.danger
                        : Theme.textPrimary
                font.bold: true
                font.pixelSize: 16
            }
            Text {
                visible: modelData.suffix !== ""
                text: modelData.suffix
                textFormat: Text.PlainText
                color: Theme.muted
                font.pixelSize: 11
            }
        }
    }
}
