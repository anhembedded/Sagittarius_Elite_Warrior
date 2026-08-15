import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// IndicatorPickerModal (BOT-088) — Modal card for selecting custom indicator scripts.
ModalDialogCard {
    id: root
    title: "CHỈ BÁO THAM KHẢO"
    iconSource: "image://icons/sliders/accent"
    width: 360
    height: 300

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    ScrollView {
        anchors.fill: parent
        anchors.margins: 14
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: root.width - 48
            spacing: 10

            Text {
                Layout.fillWidth: true
                visible: !root.hasViewModel || (viewModel.scriptModel && viewModel.scriptModel.rowCount === 0)
                text: "Chưa có tập lệnh chỉ báo nào được đăng ký."
                color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                font.pixelSize: 11
            }

            Repeater {
                model: root.hasViewModel ? viewModel.scriptModel : []

                RowLayout {
                    Layout.fillWidth: true
                    required property var model
                    required property int index

                    StyledCheck {
                        objectName: "chkBacktestScript_" + parent.model.key
                        text: parent.model.title
                        checked: parent.model.enabled
                        onToggled: {
                            if (root.hasViewModel) {
                                viewModel.scriptModel.setEnabled(parent.index, checked)
                            }
                        }
                    }
                }
            }
        }
    }
}
