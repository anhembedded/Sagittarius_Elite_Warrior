import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// Dynamic "Cấu hình Thông số Bot" form (BOT-047). Renders whatever
// `viewModel.botParamsSchema` says — a list of {group, fields} built from
// the SELECTED strategy's own declared input_*() parameters
// (BOT-044/BOT-046) — so a new strategy with different parameters needs no
// change here at all, only a `.register()` call.
//
// Field widgets are picked purely from each row's `kind` (int/float/bool/
// string), never from the strategy's identity — that is what keeps this
// component strategy-agnostic. Every group uses the same "sliders" icon
// (matching the toolbar button that opens this dialog) rather than guessing
// an icon from the group's name text, which would be exactly the kind of
// per-strategy hardcoding this mechanism exists to avoid.
Popup {
    id: root
    property string strategyName: ""
    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    width: 650
    height: Math.min(600, contentColumn.implicitHeight + 170)
    modal: true
    dim: true
    anchors.centerIn: Overlay.overlay
    padding: 20

    background: Rectangle {
        color: Theme && Theme.bg ? Theme.bg : "#141620"
        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
        border.width: 1
        radius: 8
    }

    // Closed by the Presenter's own signal, not a local `root.close()` call
    // in the save handler — a validation failure must leave the dialog open
    // (see requestBotParamsSave below), so only a genuine save success ever
    // triggers this.
    Connections {
        target: typeof viewModel === "undefined" ? null : viewModel
        function onBotParamsSaved() { root.close() }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 14

        // ================= Title =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Image {
                source: "image://icons/sliders/accent"
                sourceSize: Qt.size(16, 16)
            }
            Text {
                text: "CẤU HÌNH THÔNG SỐ BOT: " + root.strategyName.toUpperCase()
                color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                font.pixelSize: 13
                font.bold: true
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            Button {
                objectName: "btnBotParamsClose"
                implicitWidth: 24
                implicitHeight: 24
                background: Rectangle { color: "transparent" }
                contentItem: Text {
                    text: "✕"
                    color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                    font.pixelSize: 14
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: root.close()
            }
        }

        // ================= Form body =================
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ColumnLayout {
                id: contentColumn
                width: root.width - 40
                spacing: 16

                Text {
                    Layout.fillWidth: true
                    visible: typeof viewModel !== "undefined" && viewModel.botParamsSchema.length === 0
                    text: "Chiến lược này không có tham số nào để cấu hình."
                    color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                }

                Repeater {
                    model: typeof viewModel === "undefined" ? [] : viewModel.botParamsSchema

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: groupColumn.implicitHeight + 24
                        color: Theme && Theme.stateIdleBg ? Theme.stateIdleBg : "#181a24"
                        border.color: Theme && Theme.border ? Theme.border : "#2a2d3d"
                        border.width: 1
                        radius: 6

                        ColumnLayout {
                            id: groupColumn
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 10

                            RowLayout {
                                spacing: 6
                                visible: modelData.group !== ""

                                Image {
                                    source: "image://icons/sliders/muted"
                                    sourceSize: Qt.size(12, 12)
                                }
                                Text {
                                    text: modelData.group
                                    color: Theme.textPrimary
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.letterSpacing: 1
                                }
                            }

                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: 16
                                rowSpacing: 12

                                Repeater {
                                    model: modelData.fields

                                    BotParamField {
                                        Layout.fillWidth: true
                                        fieldData: modelData
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ================= Error =================
        Text {
            objectName: "txtBotParamsError"
            Layout.fillWidth: true
            visible: typeof viewModel !== "undefined" && viewModel.botParamsError !== ""
            text: typeof viewModel === "undefined" ? "" : viewModel.botParamsError
            color: "#ff5252"
            font.pixelSize: 11
            wrapMode: Text.Wrap
        }

        // ================= Footer =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Button {
                objectName: "btnBotParamsReset"
                text: "Khôi phục Mặc định"
                implicitHeight: 32
                background: Rectangle { color: "transparent"; border.color: Theme.border; radius: 4 }
                contentItem: Text {
                    text: parent.text
                    color: Theme.muted
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: root.resetAllFields()
            }

            Item { Layout.fillWidth: true }

            Button {
                objectName: "btnBotParamsCancel"
                text: "Hủy"
                implicitHeight: 32
                background: Rectangle { color: "transparent"; border.color: Theme.border; radius: 4 }
                contentItem: Text {
                    text: parent.text
                    color: Theme.textPrimary
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: root.close()
            }

            Button {
                objectName: "btnBotParamsSave"
                text: "Lưu & Re-Backtest"
                implicitWidth: 150
                implicitHeight: 32
                background: Rectangle { color: Theme.accent; radius: 4 }
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
        }
    }

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
