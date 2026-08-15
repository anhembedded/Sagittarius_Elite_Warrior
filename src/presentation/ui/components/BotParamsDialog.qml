import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// Dynamic "Cấu hình Thông số Bot" form (BOT-047/BOT-088). Renders whatever
// `viewModel.botParamsSchema` says using the unified ModalDialogCard frame.
ModalDialogCard {
    id: root
    property string strategyName: ""
    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    title: "CẤU HÌNH THÔNG SỐ BOT: " + root.strategyName.toUpperCase()
    iconSource: "image://icons/sliders/accent"
    width: 650
    height: Math.min(600, contentColumn.implicitHeight + 170)

    // Closed by the Presenter's own signal, not a local `root.close()` call
    // in the save handler — a validation failure must leave the dialog open
    // (see requestBotParamsSave below), so only a genuine save success ever
    // triggers this.
    Connections {
        target: typeof viewModel === "undefined" ? null : viewModel
        function onBotParamsSaved() { root.close() }
    }

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            id: contentColumn
            width: root.width - 48
            spacing: 16

            Text {
                Layout.fillWidth: true
                visible: typeof viewModel !== "undefined" && viewModel.botParamsSchema.length === 0
                text: "Chiến lược này không có tham số nào để cấu hình."
                color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                font.pixelSize: 11
            }

            Repeater {
                model: typeof viewModel === "undefined" ? [] : viewModel.botParamsSchema

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    required property var modelData
                    required property int index

                    // Group Header
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Image {
                            source: "image://icons/sliders/accent"
                            sourceSize: Qt.size(13, 13)
                        }

                        Text {
                            text: parent.parent.modelData.group.toUpperCase()
                            color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                            font.pixelSize: 11
                            font.bold: true
                            font.letterSpacing: 0.5
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                        }
                    }

                    // Field Grid: 2 columns per group
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 14
                        rowSpacing: 10

                        Repeater {
                            model: parent.parent.modelData.fields

                            BotParamField {
                                Layout.fillWidth: true
                                required property var modelData
                                required property int index

                                fieldData: modelData
                            }
                        }
                    }
                }
            }
        }
    }

    footerData: [
        Button {
            text: "Đặt lại mặc định"
            implicitHeight: 32
            background: Rectangle {
                color: "transparent"
                border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                radius: 6
            }
            contentItem: Text {
                text: parent.text
                color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            onClicked: root.resetAllFields()
        },

        Item { Layout.fillWidth: true },

        Button {
            objectName: "btnBotParamsCancel"
            text: "Hủy"
            implicitHeight: 32
            implicitWidth: 70
            background: Rectangle {
                color: parent.hovered ? "#2e3247" : "#242738"
                radius: 6
            }
            contentItem: Text {
                text: parent.text
                color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            onClicked: root.close()
        },

        Button {
            objectName: "btnBotParamsSave"
            text: "Lưu & Re-Backtest"
            implicitWidth: 150
            implicitHeight: 32
            background: Rectangle {
                color: parent.hovered ? "#ffd033" : (Theme && Theme.accent ? Theme.accent : "#f0b90b")
                radius: 6
            }
            contentItem: Text {
                text: parent.text
                color: "#000000"
                font.pixelSize: 11
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            onClicked: root.saveAndRerun()
        }
    ]

    // Every BotParamField sets `isBotParamField: true` — walking the tree
    // for that marker (rather than keeping a second flat list in sync with
    // the nested group/field Repeaters above) means Reset/Save work
    // regardless of how deeply the form is nested.
    function _collectFieldItems(item, result) {
        for (var i = 0; i < item.children.length; ++i) {
            var child = item.children[i]
            if (child.isBotParamField === true) {
                result.push(child)
            }
            _collectFieldItems(child, result)
        }
    }

    function resetAllFields() {
        var items = []
        _collectFieldItems(contentColumn, items)
        for (var i = 0; i < items.length; ++i) {
            items[i].resetToDefault()
        }
    }

    function saveAndRerun() {
        var items = []
        _collectFieldItems(contentColumn, items)
        var values = ({})
        for (var i = 0; i < items.length; ++i) {
            values[items[i].fieldName] = items[i].currentValue
        }
        viewModel.requestBotParamsSave(values)
    }
}
