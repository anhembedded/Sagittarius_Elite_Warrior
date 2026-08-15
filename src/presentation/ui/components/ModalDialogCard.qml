import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// ModalDialogCard (BOT-088) — Shared abstraction layer for modal card dialogs.
// Provides standardized card styling (dark theme, rounded border, elevation),
// header with icon, title, subtitle, close button, body slot, and optional footer.
Popup {
    id: root

    // ================= Public Properties =================
    property string title: ""
    property string subtitle: ""
    property string iconSource: ""
    property int iconSize: 16
    property bool showCloseButton: true
    property bool showHeaderSeparator: true
    property int cardRadius: 10
    property color cardBg: (typeof Theme !== "undefined" && Theme && Theme.bgCard) ? Theme.bgCard : "#141620"
    property color cardBorderColor: (typeof Theme !== "undefined" && Theme && Theme.border) ? Theme.border : "#282c3f"
    property color titleColor: (typeof Theme !== "undefined" && Theme && Theme.textPrimary) ? Theme.textPrimary : "#e5e7eb"
    property color mutedColor: (typeof Theme !== "undefined" && Theme && Theme.muted) ? Theme.muted : "#9aa4b2"

    // Content container slot
    default property alias bodyData: bodyContainer.data
    property alias footerData: footerContainer.data
    property bool hasFooter: footerContainer.children.length > 0

    modal: true
    dim: true
    anchors.centerIn: Overlay.overlay
    padding: 0

    background: Rectangle {
        color: root.cardBg
        border.color: root.cardBorderColor
        border.width: 1
        radius: root.cardRadius
    }

    contentItem: ColumnLayout {
        spacing: 0

        // ================= Header =================
        Rectangle {
            id: headerArea
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            color: "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 10

                Image {
                    visible: root.iconSource !== ""
                    source: root.iconSource
                    sourceSize: Qt.size(root.iconSize, root.iconSize)
                    Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Layout.alignment: Qt.AlignVCenter

                    Text {
                        text: root.title
                        color: root.titleColor
                        font.pixelSize: 12
                        font.bold: true
                        font.letterSpacing: 0.8
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        visible: root.subtitle !== ""
                        text: root.subtitle
                        color: root.mutedColor
                        font.pixelSize: 11
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                Button {
                    objectName: "btnModalClose"
                    visible: root.showCloseButton
                    implicitWidth: 26
                    implicitHeight: 26
                    background: Rectangle {
                        color: parent.hovered ? "#242738" : "transparent"
                        radius: 6
                    }
                    contentItem: Text {
                        text: "✕"
                        color: root.mutedColor
                        font.pixelSize: 13
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: root.close()
                }
            }

            Rectangle {
                visible: root.showHeaderSeparator
                width: parent.width
                height: 1
                color: root.cardBorderColor
                anchors.bottom: parent.bottom
            }
        }

        // ================= Body Container =================
        Item {
            id: bodyContainer
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        // ================= Footer Container =================
        Rectangle {
            id: footerArea
            visible: root.hasFooter
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            color: "transparent"

            Rectangle {
                width: parent.width
                height: 1
                color: root.cardBorderColor
                anchors.top: parent.top
            }

            RowLayout {
                id: footerContainer
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 8
            }
        }
    }
}
