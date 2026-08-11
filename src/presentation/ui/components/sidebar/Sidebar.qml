import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Navigation sidebar (BOT-030 Phase 1) — QML replacement for the QtWidgets
// sidebar built in BOT-029 Phase 1, keeping the same visual design:
// brand cluster, titled sections, and a dimmed placeholder entry for
// screens that don't exist yet.
Rectangle {
    id: root

    // Natural width of the nav rail. QQuickWidget derives its sizeHint from
    // the QML root's implicit size, so without this the hosting widget
    // reports 0x0 and the shell layout collapses the sidebar to nothing
    // (the QtWidgets version got its width from QPushButton size hints).
    implicitWidth: 220

    color: Theme.bgSidebar

    // Right-edge separator, matching the QSS `border-right` the widget
    // version used (Rectangle has no per-side border).
    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: Theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        anchors.topMargin: 20
        spacing: 10

        // ---- Brand cluster -------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "SAGITTARIUS"
                color: Theme.accent
                font.pixelSize: 16
                font.bold: true
            }

            Rectangle {
                radius: 3
                color: Theme.accent
                Layout.preferredWidth: tagText.implicitWidth + 10
                Layout.preferredHeight: tagText.implicitHeight + 2

                Text {
                    id: tagText
                    anchors.centerIn: parent
                    text: "ELITE WARRIOR"
                    color: Theme.bg
                    font.pixelSize: 10
                    font.bold: true
                }
            }

            Item { Layout.fillWidth: true }
        }

        Item { Layout.preferredHeight: 10 }

        // ---- Sections ------------------------------------------------
        Repeater {
            model: viewModel ? viewModel.sections : null

            ColumnLayout {
                required property var modelData

                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: modelData.title
                    color: "#5b6270"
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 1
                    Layout.topMargin: 6
                    Layout.leftMargin: 4
                }

                Repeater {
                    model: modelData.items

                    Button {
                        id: navButton
                        required property var modelData

                        // Lets tests address a specific entry without
                        // depending on layout order or coordinates.
                        objectName: "navButton_" + (modelData.route || modelData.label)

                        text: modelData.label
                        enabled: modelData.navigable
                        Layout.fillWidth: true
                        Layout.preferredHeight: 40

                        readonly property bool isActive:
                            modelData.navigable && viewModel && modelData.route === viewModel.activeRoute

                        ToolTip.visible: !modelData.navigable && hovered
                        ToolTip.text: "Coming soon"

                        onClicked: { if (viewModel) viewModel.navigate(modelData.route) }

                        background: Rectangle {
                            radius: 6
                            color: navButton.isActive
                                   ? Qt.rgba(0.95, 0.73, 0.18, 0.12)
                                   : (navButton.hovered && navButton.enabled
                                      ? "#1f2127" : "#17181d")
                            border.width: 1
                            border.color: navButton.isActive ? Theme.accent : "#2a2d36"
                            opacity: navButton.enabled ? 1.0 : 0.45
                        }

                        contentItem: RowLayout {
                            spacing: 8

                            Image {
                                source: "image://icons/" + navButton.modelData.icon
                                        + "/" + (navButton.isActive ? "accent" : "muted")
                                sourceSize.width: 18
                                sourceSize.height: 18
                                Layout.preferredWidth: 18
                                Layout.preferredHeight: 18
                                opacity: navButton.enabled ? 1.0 : 0.45
                            }

                            Text {
                                text: navButton.text
                                color: navButton.isActive ? Theme.accent : Theme.textPrimary
                                font.pixelSize: 13
                                opacity: navButton.enabled ? 1.0 : 0.45
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }
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
            Layout.leftMargin: -10
            Layout.rightMargin: -10
            visible: viewModel ? viewModel.bottomActions.length > 0 : false
        }

        Repeater {
            model: viewModel ? viewModel.bottomActions : null

            Button {
                id: bottomNavButton
                required property var modelData

                objectName: "bottomNavButton_" + (modelData.route || modelData.label)

                text: modelData.label
                enabled: modelData.navigable
                Layout.fillWidth: true
                Layout.preferredHeight: 40

                readonly property bool isActive:
                    modelData.navigable && viewModel && modelData.route === viewModel.activeRoute

                ToolTip.visible: !modelData.navigable && hovered
                ToolTip.text: "Coming soon"

                onClicked: { if (viewModel) viewModel.navigate(modelData.route) }

                background: Rectangle {
                    radius: 6
                    color: bottomNavButton.isActive
                           ? Qt.rgba(0.95, 0.73, 0.18, 0.12)
                           : (bottomNavButton.hovered && bottomNavButton.enabled
                              ? "#1f2127" : "#17181d")
                    border.width: 1
                    border.color: bottomNavButton.isActive ? Theme.accent : "#2a2d36"
                    opacity: bottomNavButton.enabled ? 1.0 : 0.45
                }

                contentItem: RowLayout {
                    spacing: 8

                    Image {
                        source: "image://icons/" + bottomNavButton.modelData.icon
                                + "/" + (bottomNavButton.isActive ? "accent" : "muted")
                        sourceSize.width: 18
                        sourceSize.height: 18
                        Layout.preferredWidth: 18
                        Layout.preferredHeight: 18
                        opacity: bottomNavButton.enabled ? 1.0 : 0.45
                    }

                    Text {
                        text: bottomNavButton.text
                        color: bottomNavButton.isActive ? Theme.accent : Theme.textPrimary
                        font.pixelSize: 13
                        opacity: bottomNavButton.enabled ? 1.0 : 0.45
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
}
