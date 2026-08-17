import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// TimezonePickerModal (BOT-097) — Modal dialog for selecting display timezone.
// Note: Display concern only — data/engine/database always remain UTC.
ModalDialogCard {
    id: root
    title: "CHỌN MÚI GIỜ HIỂN THỊ"
    subtitle: "Chỉ đổi giờ hiển thị. Dữ liệu và Backtest luôn tính theo UTC."
    iconSource: "image://icons/clock/accent"
    preferredWidth: 440
    preferredHeight: 350

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8

        ListView {
            id: tzListView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            boundsBehavior: Flickable.StopAtBounds

            model: root.hasViewModel ? viewModel.displayTimezoneOptions : [
                { "id": "UTC", "label": "UTC (Giờ phối hợp quốc tế)", "shortLabel": "UTC" },
                { "id": "SYSTEM", "label": "Giờ hệ thống (Local)", "shortLabel": "Hệ thống" },
                { "id": "Asia/Ho_Chi_Minh", "label": "Asia/Ho_Chi_Minh (Việt Nam / GMT+7)", "shortLabel": "Asia/Ho_Chi_Minh" },
                { "id": "Asia/Tokyo", "label": "Asia/Tokyo (Nhật Bản / GMT+9)", "shortLabel": "Asia/Tokyo" },
                { "id": "Europe/London", "label": "Europe/London (Anh)", "shortLabel": "Europe/London" },
                { "id": "America/New_York", "label": "America/New_York (Mỹ - Eastern)", "shortLabel": "America/New_York" }
            ]

            delegate: Button {
                id: tzItemBtn
                width: tzListView.width
                implicitHeight: 40
                objectName: "tzItem_" + modelData.id

                readonly property bool isSelected: root.hasViewModel && modelData.id === viewModel.displayTimezone

                background: Rectangle {
                    color: tzItemBtn.isSelected
                           ? ((Theme && Theme.bgSecondary) ? Theme.bgSecondary : "#242738")
                           : (tzItemBtn.hovered
                              ? ((Theme && Theme.bgCardHover) ? Theme.bgCardHover : "#1b1d28")
                              : ((Theme && Theme.bgCard) ? Theme.bgCard : "#141620"))
                    border.color: tzItemBtn.isSelected
                                  ? ((Theme && Theme.accent) ? Theme.accent : "#f0b90b")
                                  : ((Theme && Theme.border) ? Theme.border : "#2a2d3e")
                    border.width: tzItemBtn.isSelected ? 1.5 : 1
                    radius: 8

                    Behavior on color {
                        ColorAnimation { duration: 150 }
                    }
                }

                contentItem: RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8

                    Image {
                        source: "image://icons/clock/accent"
                        sourceSize: Qt.size(13, 13)
                        opacity: tzItemBtn.isSelected ? 1.0 : 0.6
                    }

                    Text {
                        text: modelData.label
                        textFormat: Text.PlainText
                        color: tzItemBtn.isSelected
                               ? ((Theme && Theme.accent) ? Theme.accent : "#f0b90b")
                               : ((Theme && Theme.textPrimary) ? Theme.textPrimary : "#e5e7eb")
                        font.pixelSize: 12
                        font.bold: tzItemBtn.isSelected
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                        verticalAlignment: Text.AlignVCenter
                    }

                    Text {
                        visible: tzItemBtn.isSelected
                        text: "✓"
                        textFormat: Text.PlainText
                        color: (Theme && Theme.accent) ? Theme.accent : "#f0b90b"
                        font.pixelSize: 13
                        font.bold: true
                    }
                }

                onClicked: {
                    if (root.hasViewModel) {
                        viewModel.setDisplayTimezone(modelData.id)
                    }
                    root.close()
                }
            }
        }
    }
}
