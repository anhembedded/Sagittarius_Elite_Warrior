import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// "CHỈ BÁO THAM KHẢO" dropdown (BOT-064) — lets the user enable indicator
// scripts on the Backtest chart, independent of the selected strategy's own
// indicators (BOT-060). Same viewModel.scriptModel shape
// (IndicatorScriptListModel) DevBoardPanel.qml's "CUSTOM SCRIPTS" checklist
// already uses — a script enabled here shows up on the Backtest chart the
// next time "Chạy Backtest" runs (no retroactive effect, same rule the Dev
// Board checklist follows).
Popup {
    id: root
    width: 260
    padding: 0
    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    background: Rectangle {
        color: Theme && Theme.bgCard ? Theme.bgCard : "#141620"
        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
        radius: 6
    }

    contentItem: ColumnLayout {
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: "transparent"

            Text {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                verticalAlignment: Text.AlignVCenter
                text: "Chỉ báo tham khảo"
                color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                font.pixelSize: 12
                font.bold: true
            }

            Rectangle {
                width: parent.width
                height: 1
                color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                anchors.bottom: parent.bottom
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 10
            spacing: 8

            Repeater {
                model: typeof viewModel === "undefined" ? [] : viewModel.scriptModel

                RowLayout {
                    Layout.fillWidth: true
                    required property var model
                    required property int index

                    StyledCheck {
                        objectName: "chkBacktestScript_" + parent.model.key
                        text: parent.model.title
                        checked: parent.model.enabled
                        onToggled: viewModel.scriptModel.setEnabled(parent.index, checked)
                    }
                }
            }
        }
    }
}
