import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// StrategyPickerModal — Modal dialog for selecting active trading strategy.
ModalDialogCard {
    id: root
    title: "CHỌN CHIẾN LƯỢC BOT"
    iconSource: "image://icons/briefcase/accent"
    preferredWidth: 440
    preferredHeight: 320

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    ScrollView {
        anchors.fill: parent
        anchors.margins: 14
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: root.width - 48
            spacing: 8

            Repeater {
                model: root.hasViewModel ? viewModel.strategyOptions : []

                ItemDelegate {
                    id: delegateItem
                    Layout.fillWidth: true
                    implicitHeight: 46
                    required property var modelData
                    required property int index

                    readonly property bool isSelected: root.hasViewModel && modelData.key === viewModel.selectedStrategyKey

                    background: Rectangle {
                        color: delegateItem.isSelected ? "#242738" : (delegateItem.hovered ? "#181a24" : "transparent")
                        border.color: delegateItem.isSelected ? (Theme && Theme.accent ? Theme.accent : "#f0b90b") : (Theme && Theme.border ? Theme.border : "#2a2d3e")
                        border.width: 1
                        radius: 8
                    }

                    contentItem: RowLayout {
                        spacing: 12
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12

                        Image {
                            source: "image://icons/briefcase/accent"
                            sourceSize: Qt.size(15, 15)
                            opacity: delegateItem.isSelected ? 1.0 : 0.6
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: delegateItem.modelData.name
                                color: delegateItem.isSelected ? (Theme && Theme.accent ? Theme.accent : "#f0b90b") : (Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb")
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Text {
                                text: "Mã: " + delegateItem.modelData.key
                                color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                                font.pixelSize: 10
                            }
                        }

                        Rectangle {
                            visible: delegateItem.isSelected
                            implicitWidth: 8
                            implicitHeight: 8
                            radius: 4
                            color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                        }
                    }

                    onClicked: {
                        if (root.hasViewModel) {
                            viewModel.selectedStrategyKey = modelData.key
                        }
                        root.close()
                    }
                }
            }
        }
    }
}
