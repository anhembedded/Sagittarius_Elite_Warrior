import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

// LimitationsModal (BOT-088) — Modal card for displaying the active limitations/assumptions of the current backtest run.
ModalDialogCard {
    id: root
    objectName: "limitationsPopup"
    title: "GIỚI HẠN CỦA LẦN CHẠY NÀY"
    iconSource: "image://icons/info/accent"
    width: 480
    height: 420

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: root.width - 48
            spacing: 10

            Repeater {
                model: root.hasViewModel ? viewModel.limitations : []
                delegate: RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "•"
                        color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                        font.pixelSize: 13
                        font.bold: true
                        Layout.alignment: Qt.AlignTop
                    }
                    Text {
                        objectName: "lblLimitation_" + index
                        Layout.fillWidth: true
                        text: modelData
                        color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }
}
