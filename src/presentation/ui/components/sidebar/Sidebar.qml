import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// Navigation sidebar (VS Code Activity Bar style):
// Supports full expanded view (220px) and sleek compact icon-only rail (48px)
// with left accent indicators and hover tooltips.
Rectangle {
    id: root

    implicitWidth: (viewModel && viewModel.isCollapsed) ? 48 : 220

    color: Theme.bgSidebar

    // Right-edge separator
    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: Theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: (viewModel && viewModel.isCollapsed) ? 4 : 10
        anchors.topMargin: (viewModel && viewModel.isCollapsed) ? 10 : 16
        spacing: 8

        // ---- Brand & Toggle Header -------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            // When NOT collapsed: Full Brand Title
            Text {
                visible: !(viewModel && viewModel.isCollapsed)
                text: "SAGITTARIUS"
                color: Theme.accent
                font.pixelSize: 15
                font.bold: true
                Layout.alignment: Qt.AlignVCenter
            }

            Rectangle {
                visible: !(viewModel && viewModel.isCollapsed)
                radius: 3
                color: Theme.accent
                Layout.preferredWidth: tagText.implicitWidth + 8
                Layout.preferredHeight: tagText.implicitHeight + 2
                Layout.alignment: Qt.AlignVCenter

                Text {
                    id: tagText
                    anchors.centerIn: parent
                    text: "ELITE"
                    color: Theme.bg
                    font.pixelSize: 9
                    font.bold: true
                }
            }

            Item {
                visible: !(viewModel && viewModel.isCollapsed)
                Layout.fillWidth: true
            }

            // Sleek Toggle Button (VS Code style panel icon)
            StatefulButton {
                id: btnCollapse
                objectName: "btnCollapseSidebar"
                iconSource: (viewModel && viewModel.isCollapsed) ? "panel-left" : "panel-left"
                iconSize: 16
                implicitHeight: (viewModel && viewModel.isCollapsed) ? 36 : 28
                Layout.preferredWidth: (viewModel && viewModel.isCollapsed) ? 36 : 28
                Layout.alignment: (viewModel && viewModel.isCollapsed) ? Qt.AlignHCenter : Qt.AlignVCenter
                accentBorder: "transparent"
                idleBgColor: "transparent"
                hoverBgColor: Theme.stateHoverBg

                ToolTip.visible: hovered
                ToolTip.text: (viewModel && viewModel.isCollapsed) ? "Mở rộng thanh bên" : "Thu gọn thanh bên"

                onClicked: {
                    if (viewModel) viewModel.toggleCollapsed()
                }
            }
        }

        Item { Layout.preferredHeight: (viewModel && viewModel.isCollapsed) ? 4 : 8 }

        // ---- Sections ------------------------------------------------
        Repeater {
            model: viewModel ? viewModel.sections : null

            ColumnLayout {
                required property var modelData

                Layout.fillWidth: true
                spacing: (viewModel && viewModel.isCollapsed) ? 6 : 8

                Text {
                    visible: !(viewModel && viewModel.isCollapsed)
                    text: modelData.title
                    color: "#5b6270"
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 1
                    Layout.topMargin: 4
                    Layout.leftMargin: 4
                }

                Rectangle {
                    visible: (viewModel && viewModel.isCollapsed)
                    Layout.alignment: Qt.AlignHCenter
                    width: 24
                    height: 1
                    color: Theme.border
                    opacity: 0.4
                    Layout.topMargin: 2
                    Layout.bottomMargin: 2
                }

                Repeater {
                    model: modelData.items

                    Item {
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: (viewModel && viewModel.isCollapsed) ? 38 : 40

                        StatefulButton {
                            id: navBtn
                            objectName: "navButton_" + (modelData.route || modelData.label)

                            anchors.centerIn: (viewModel && viewModel.isCollapsed) ? parent : undefined
                            anchors.fill: !(viewModel && viewModel.isCollapsed) ? parent : undefined
                            width: (viewModel && viewModel.isCollapsed) ? 36 : undefined
                            height: (viewModel && viewModel.isCollapsed) ? 36 : undefined

                            text: (viewModel && viewModel.isCollapsed) ? "" : modelData.label
                            enabled: modelData.navigable
                            implicitHeight: (viewModel && viewModel.isCollapsed) ? 36 : 40

                            iconSource: modelData.icon
                            iconSize: (viewModel && viewModel.isCollapsed) ? 19 : 18
                            fontSize: 13
                            contentSpacing: (viewModel && viewModel.isCollapsed) ? 0 : 8
                            textFillWidth: !(viewModel && viewModel.isCollapsed)
                            accentBorder: (viewModel && viewModel.isCollapsed) ? "transparent" : Theme.stateNavBorder
                            isActive: modelData.navigable && viewModel && modelData.route === viewModel.activeRoute

                            ToolTip.visible: ((viewModel && viewModel.isCollapsed) || !modelData.navigable) && hovered
                            ToolTip.text: modelData.tooltip ? modelData.tooltip : (!modelData.navigable ? (modelData.label + " (Sắp ra mắt)") : modelData.label)

                            onClicked: { if (viewModel) viewModel.navigate(modelData.route) }
                        }

                        // VS Code style left vertical indicator for active route
                        Rectangle {
                            visible: (viewModel && viewModel.isCollapsed) && (modelData.navigable && viewModel && modelData.route === viewModel.activeRoute)
                            anchors.left: parent.left
                            anchors.leftMargin: -3
                            anchors.verticalCenter: parent.verticalCenter
                            width: 3
                            height: 22
                            radius: 1.5
                            color: Theme.accent
                        }
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        // ---- Bottom Actions (Settings) -------------------------------
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            Layout.leftMargin: (viewModel && viewModel.isCollapsed) ? 4 : -10
            Layout.rightMargin: (viewModel && viewModel.isCollapsed) ? 4 : -10
            opacity: (viewModel && viewModel.isCollapsed) ? 0.4 : 1.0
            visible: viewModel ? viewModel.bottomActions.length > 0 : false
        }

        Repeater {
            model: viewModel ? viewModel.bottomActions : null

            Item {
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: (viewModel && viewModel.isCollapsed) ? 38 : 40

                StatefulButton {
                    id: bottomNavBtn
                    objectName: "bottomNavButton_" + (modelData.route || modelData.label)

                    anchors.centerIn: (viewModel && viewModel.isCollapsed) ? parent : undefined
                    anchors.fill: !(viewModel && viewModel.isCollapsed) ? parent : undefined
                    width: (viewModel && viewModel.isCollapsed) ? 36 : undefined
                    height: (viewModel && viewModel.isCollapsed) ? 36 : undefined

                    text: (viewModel && viewModel.isCollapsed) ? "" : modelData.label
                    enabled: modelData.navigable
                    implicitHeight: (viewModel && viewModel.isCollapsed) ? 36 : 40

                    iconSource: modelData.icon
                    iconSize: (viewModel && viewModel.isCollapsed) ? 19 : 18
                    fontSize: 13
                    contentSpacing: (viewModel && viewModel.isCollapsed) ? 0 : 8
                    textFillWidth: !(viewModel && viewModel.isCollapsed)
                    accentBorder: (viewModel && viewModel.isCollapsed) ? "transparent" : Theme.stateNavBorder
                    isActive: modelData.navigable && viewModel && modelData.route === viewModel.activeRoute

                    ToolTip.visible: ((viewModel && viewModel.isCollapsed) || !modelData.navigable) && hovered
                    ToolTip.text: modelData.tooltip ? modelData.tooltip : (!modelData.navigable ? (modelData.label + " (Sắp ra mắt)") : modelData.label)

                    onClicked: { if (viewModel) viewModel.navigate(modelData.route) }
                }

                // VS Code style left vertical indicator for active bottom action
                Rectangle {
                    visible: (viewModel && viewModel.isCollapsed) && (modelData.navigable && viewModel && modelData.route === viewModel.activeRoute)
                    anchors.left: parent.left
                    anchors.leftMargin: -3
                    anchors.verticalCenter: parent.verticalCenter
                    width: 3
                    height: 22
                    radius: 1.5
                    color: Theme.accent
                }
            }
        }
    }
}

