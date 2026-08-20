import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// Navigation sidebar (BOT-030 / Collapsible Nav Rail):
// Supports full expanded view (220px) and compact icon-only rail (64px)
// with smooth toggle transition and tooltips.
Rectangle {
    id: root

    implicitWidth: (viewModel && viewModel.isCollapsed) ? 64 : 220

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
        anchors.margins: (viewModel && viewModel.isCollapsed) ? 6 : 10
        anchors.topMargin: 16
        spacing: 10

        // ---- Brand & Toggle cluster -------------------------------------------
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

            // When COLLAPSED: Mini Logo "S"
            Rectangle {
                visible: (viewModel && viewModel.isCollapsed)
                radius: 4
                color: Theme.accent
                Layout.preferredWidth: 26
                Layout.preferredHeight: 26
                Layout.alignment: Qt.AlignHCenter

                Text {
                    anchors.centerIn: parent
                    text: "S"
                    color: Theme.bg
                    font.pixelSize: 14
                    font.bold: true
                }
            }

            Item { Layout.fillWidth: true }

            // Toggle collapse/expand button
            StatefulButton {
                id: btnCollapse
                objectName: "btnCollapseSidebar"
                iconSource: (viewModel && viewModel.isCollapsed) ? "chevron-right" : "chevron-left"
                iconSize: 14
                implicitHeight: 28
                Layout.preferredWidth: 28
                Layout.alignment: Qt.AlignVCenter
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

        Item { Layout.preferredHeight: 6 }

        // ---- Sections ------------------------------------------------
        Repeater {
            model: viewModel ? viewModel.sections : null

            ColumnLayout {
                required property var modelData

                Layout.fillWidth: true
                spacing: (viewModel && viewModel.isCollapsed) ? 6 : 10

                Text {
                    visible: !(viewModel && viewModel.isCollapsed)
                    text: modelData.title
                    color: "#5b6270"
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 1
                    Layout.topMargin: 6
                    Layout.leftMargin: 4
                }

                Rectangle {
                    visible: (viewModel && viewModel.isCollapsed)
                    Layout.fillWidth: true
                    height: 1
                    color: Theme.border
                    opacity: 0.6
                    Layout.topMargin: 4
                    Layout.bottomMargin: 4
                }

                Repeater {
                    model: modelData.items

                    StatefulButton {
                        required property var modelData

                        // Lets tests address a specific entry without
                        // depending on layout order or coordinates.
                        objectName: "navButton_" + (modelData.route || modelData.label)

                        text: (viewModel && viewModel.isCollapsed) ? "" : modelData.label
                        enabled: modelData.navigable
                        Layout.fillWidth: true
                        implicitHeight: 40

                        iconSource: modelData.icon
                        iconSize: 18
                        fontSize: 13
                        contentSpacing: (viewModel && viewModel.isCollapsed) ? 0 : 8
                        textFillWidth: !(viewModel && viewModel.isCollapsed)
                        accentBorder: Theme.stateNavBorder
                        isActive: modelData.navigable && viewModel && modelData.route === viewModel.activeRoute

                        ToolTip.visible: ((viewModel && viewModel.isCollapsed) || !modelData.navigable) && hovered
                        ToolTip.text: !modelData.navigable ? (modelData.label + " (Sắp ra mắt)") : modelData.label

                        onClicked: { if (viewModel) viewModel.navigate(modelData.route) }
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        // ---- Bottom Actions ------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            Layout.leftMargin: (viewModel && viewModel.isCollapsed) ? -6 : -10
            Layout.rightMargin: (viewModel && viewModel.isCollapsed) ? -6 : -10
            visible: viewModel ? viewModel.bottomActions.length > 0 : false
        }

        Repeater {
            model: viewModel ? viewModel.bottomActions : null

            StatefulButton {
                required property var modelData

                objectName: "bottomNavButton_" + (modelData.route || modelData.label)

                text: (viewModel && viewModel.isCollapsed) ? "" : modelData.label
                enabled: modelData.navigable
                Layout.fillWidth: true
                implicitHeight: 40

                iconSource: modelData.icon
                iconSize: 18
                fontSize: 13
                contentSpacing: (viewModel && viewModel.isCollapsed) ? 0 : 8
                textFillWidth: !(viewModel && viewModel.isCollapsed)
                accentBorder: Theme.stateNavBorder
                isActive: modelData.navigable && viewModel && modelData.route === viewModel.activeRoute

                ToolTip.visible: ((viewModel && viewModel.isCollapsed) || !modelData.navigable) && hovered
                ToolTip.text: !modelData.navigable ? (modelData.label + " (Sắp ra mắt)") : modelData.label

                onClicked: { if (viewModel) viewModel.navigate(modelData.route) }
            }
        }
    }
}

