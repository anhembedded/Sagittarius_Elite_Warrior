import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

Item {
    id: root

    property real value: 0
    property real from: 0
    property real to: 100
    property bool indeterminate: false
    property string statusText: ""
    property string percentageText: ""
    property bool showPercentage: true
    property bool showStatusText: statusText !== ""
    property color barColor: Theme && Theme.accent ? Theme.accent : "#f0b90b"
    property color barEndColor: "#00f0ff"
    property color trackColor: "#171922"
    property color trackBorderColor: "#2a2d3d"
    property real barHeight: 6
    property real radius: 3

    readonly property real progressRatio: {
        if (to <= from) return 0.0;
        return Math.min(1.0, Math.max(0.0, (value - from) / (to - from)));
    }

    readonly property string computedPercentText: {
        if (percentageText !== "") return percentageText;
        if (indeterminate) return "";
        var pct = progressRatio * 100.0;
        return (Math.round(pct * 10) / 10).toFixed(1) + "%";
    }

    implicitWidth: 200
    implicitHeight: contentCol.implicitHeight

    ColumnLayout {
        id: contentCol
        anchors.fill: parent
        spacing: 5

        // Header row with status text and percentage
        RowLayout {
            Layout.fillWidth: true
            visible: root.showStatusText || (root.showPercentage && !root.indeterminate)
            spacing: 8

            Text {
                id: txtStatus
                text: root.statusText
                color: Theme && Theme.textSecondary ? Theme.textSecondary : "#94a3b8"
                font.pixelSize: 11
                elide: Text.ElideRight
                textFormat: Text.PlainText
                Layout.fillWidth: true
                visible: root.showStatusText
            }

            Text {
                id: txtPercent
                text: root.computedPercentText
                color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                font.pixelSize: 11
                font.bold: true
                font.family: "JetBrains Mono, Fira Code, monospace"
                textFormat: Text.PlainText
                horizontalAlignment: Text.AlignRight
                visible: root.showPercentage && !root.indeterminate
            }
        }

        // Track Bar
        Rectangle {
            id: track
            Layout.fillWidth: true
            implicitHeight: root.barHeight
            color: root.trackColor
            radius: root.radius
            border.color: root.trackBorderColor
            border.width: 1
            clip: true

            // Determinate Fill Bar
            Rectangle {
                id: fillBar
                visible: !root.indeterminate
                width: Math.min(track.width, Math.max(0, track.width * root.progressRatio))
                height: parent.height
                radius: root.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: root.barColor }
                    GradientStop { position: 1.0; color: root.barEndColor }
                }

                Behavior on width {
                    NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                }
            }

            // Indeterminate Shimmering Bar
            Rectangle {
                id: indetBar
                visible: root.indeterminate
                width: parent.width * 0.35
                height: parent.height
                radius: root.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: root.barColor }
                    GradientStop { position: 1.0; color: "transparent" }
                }

                SequentialAnimation on x {
                    loops: Animation.Infinite
                    running: root.indeterminate && root.visible
                    NumberAnimation {
                        from: -indetBar.width
                        to: track.width
                        duration: 1200
                        easing.type: Easing.InOutQuad
                    }
                }
            }
        }
    }
}
