import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

ComboBox {
    id: control
    implicitWidth: 350
    implicitHeight: 32

    // Expected model elements: name, category, description
    textRole: "name"

    background: Rectangle {
        color: "transparent"
        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
        radius: 4
    }

    contentItem: Text {
        leftPadding: 10
        rightPadding: control.indicator.width + control.spacing
        text: control.displayText
        font.pixelSize: 12
        font.bold: true
        color: Theme && Theme.accent ? Theme.accent : "#fbbf24"
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    delegate: ItemDelegate {
        id: delegateItem
        width: control.popup.width
        height: 65
        highlighted: control.highlightedIndex === index
        
        background: Rectangle {
            color: delegateItem.highlighted ? "#17181d" : "transparent"
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 4

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: model.name || ""
                    color: (delegateItem.highlighted || control.currentIndex === index)
                        ? (Theme && Theme.accent ? Theme.accent : "#fbbf24")
                        : (Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb")
                    font.pixelSize: 12
                    font.bold: true
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }

                Rectangle {
                    color: "transparent"
                    border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                    radius: 4
                    implicitWidth: badgeText.implicitWidth + 12
                    implicitHeight: badgeText.implicitHeight + 6

                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: model.category || ""
                        color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                        font.pixelSize: 9
                    }
                }
            }

            Text {
                text: model.description || ""
                color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                font.pixelSize: 11
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
        }
    }
    
    popup: Popup {
        y: control.height + 4
        width: 420
        implicitHeight: contentLayout.implicitHeight
        padding: 0

        background: Rectangle {
            color: Theme && Theme.bgCard ? Theme.bgCard : "#141620"
            border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
            radius: 4
        }

        contentItem: ColumnLayout {
            id: contentLayout
            spacing: 0
            
            // Header
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 35
                color: "transparent"
                Text {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    verticalAlignment: Text.AlignVCenter
                    text: "CHIẾN LƯỢC HIỆN CÓ (STRATEGY PRESETS)"
                    color: Theme.muted
                    font.pixelSize: 10
                    font.bold: true
                }
                
                // Bottom border for header
                Rectangle {
                    width: parent.width
                    height: 1
                    color: Theme.border
                    anchors.bottom: parent.bottom
                }
            }
            
            ListView {
                id: listView
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(contentHeight, 350) // Max height before scrolling
                clip: true
                model: control.popup.visible ? control.delegateModel : null
                currentIndex: control.highlightedIndex
                ScrollIndicator.vertical: ScrollIndicator { }
            }
        }
    }
}
