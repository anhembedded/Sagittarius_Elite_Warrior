import QtQuick
import QtQuick.Layouts

// Shared stat/KPI card — kicker, one headline value, optional unit and
// badge, one caption line. Design spec: card background, border, radius,
// kicker at top, value with unit, and subtitle/badge on the third line.
Rectangle {
    id: root
    objectName: "statCard"
    color: (typeof Theme !== "undefined" && Theme && Theme.bgCard) ? Theme.bgCard : "transparent"
    border.width: 1
    border.color: (typeof Theme !== "undefined" && Theme && Theme.border) ? Theme.border : "transparent"
    radius: (typeof Theme !== "undefined" && Theme && Theme.radiusSm) ? Theme.radiusSm : 6
    implicitHeight: 82
    implicitWidth: 160

    property string title: ""
    property string value: ""
    property string suffix: ""
    property string caption: ""
    property string badgeText: ""
    //: "neutral" | "positive" | "negative" — colours `value` and, only
    //: when not "neutral", `caption` too. Never `title`/`suffix`.
    property string tone: "neutral"
    //: "neutral" | "positive" | "negative", independent of `tone` — a
    //: badge can carry its own semantic (e.g. a duration warning) unrelated
    //: to whether the headline figure is a gain or a loss.
    property string badgeTone: "neutral"

    readonly property string _valueColor: {
        if (root.tone === "positive") return Theme.success;
        if (root.tone === "negative") return Theme.danger;
        return Theme.textPrimary;
    }
    readonly property string _badgeColor: {
        if (root.badgeTone === "positive") return Theme.success;
        if (root.badgeTone === "negative") return Theme.danger;
        return Theme.textPrimary;
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 3

        Text {
            objectName: "statCardTitle"
            Layout.fillWidth: true
            text: root.title.toUpperCase()
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.bold: true
            font.letterSpacing: 0.6
            elide: Text.ElideRight
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                objectName: "statCardValue"
                text: root.value
                textFormat: Text.PlainText
                color: root._valueColor
                font.pixelSize: 20
                font.bold: true
            }

            Text {
                objectName: "statCardSuffix"
                visible: root.suffix !== ""
                text: root.suffix
                textFormat: Text.PlainText
                color: Theme.muted
                font.pixelSize: 11
            }

            Item { Layout.fillWidth: true }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            visible: root.caption !== "" || root.badgeText !== ""

            Rectangle {
                id: badgeContainer
                objectName: "statCardBadge"
                visible: root.badgeText !== ""
                color: "transparent"
                radius: 4
                border.width: 0
                border.color: root._badgeColor
                implicitWidth: badgeLabel.implicitWidth
                implicitHeight: badgeLabel.implicitHeight

                Text {
                    id: badgeLabel
                    objectName: "statCardBadgeText"
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.badgeText
                    textFormat: Text.PlainText
                    color: root._badgeColor
                    font.pixelSize: 11
                }
            }

            Text {
                objectName: "statCardCaption"
                visible: root.caption !== ""
                text: root.caption
                textFormat: Text.PlainText
                color: root.tone === "neutral" ? Theme.muted : root._valueColor
                font.pixelSize: 11
                elide: Text.ElideRight
            }

            Item { Layout.fillWidth: true }
        }
    }
}
