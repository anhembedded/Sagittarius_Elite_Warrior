import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// Reusable dynamic tab bar with styled dark theme, count badges, and indicator.
Item {
    id: root

    property var tabsModel: []
    property int currentIndex: 0
    readonly property string currentTabId: (tabsModel && tabsModel.length > currentIndex && tabsModel[currentIndex]) ? tabsModel[currentIndex].id : ""

    readonly property color themeAccent: Theme && Theme.accent ? Theme.accent : "#fbbf24"
    readonly property color themeTextPrimary: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
    readonly property color themeMuted: Theme && Theme.muted ? Theme.muted : "#9aa4b2"

    signal tabSelected(int index, string tabId)

    implicitHeight: 38
    implicitWidth: tabRow.implicitWidth

    RowLayout {
        id: tabRow
        anchors.fill: parent
        spacing: 6

        Repeater {
            model: root.tabsModel

            Rectangle {
                id: tabBtn
                readonly property bool isActive: index === root.currentIndex
                readonly property var itemData: modelData || {}
                objectName: "tabBtn_" + (itemData.id || index)

                Layout.preferredHeight: 34
                Layout.preferredWidth: tabContentRow.implicitWidth + 24
                radius: 6
                color: isActive ? "#1c1e2d" : (tabHover.hovered ? "#161722" : "transparent")
                border.color: isActive ? "#2c3045" : "transparent"
                border.width: 1

                Behavior on color { ColorAnimation { duration: 150 } }

                RowLayout {
                    id: tabContentRow
                    anchors.centerIn: parent
                    spacing: 8

                    // Active left bar dot or accent line
                    Rectangle {
                        width: 3
                        height: 12
                        radius: 1.5
                        color: root.themeAccent
                        visible: tabBtn.isActive
                    }

                    Text {
                        text: tabBtn.itemData.label || ""
                        color: tabBtn.isActive ? root.themeTextPrimary : root.themeMuted
                        font.pixelSize: 11
                        font.bold: tabBtn.isActive
                        font.letterSpacing: 0.5
                    }

                    // Count Badge
                    Rectangle {
                        visible: typeof tabBtn.itemData.badge !== "undefined" && tabBtn.itemData.badge !== null && tabBtn.itemData.badge !== ""
                        Layout.preferredWidth: badgeText.implicitWidth + 12
                        Layout.preferredHeight: 18
                        radius: 9
                        color: tabBtn.isActive ? "#272a3e" : "#141620"
                        border.color: tabBtn.isActive ? root.themeAccent : "#242738"
                        border.width: 1

                        Text {
                            id: badgeText
                            anchors.centerIn: parent
                            text: tabBtn.itemData.badge ? ("" + tabBtn.itemData.badge) : ""
                            color: tabBtn.isActive ? root.themeAccent : root.themeMuted
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                }

                MouseArea {
                    id: tabHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.currentIndex = index
                        root.tabSelected(index, tabBtn.itemData.id || "")
                    }
                }
            }
        }

        Item { Layout.fillWidth: true }
    }
}
