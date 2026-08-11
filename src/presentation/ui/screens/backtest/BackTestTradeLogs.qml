import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

Rectangle {
    id: root
    implicitWidth: 1200
    implicitHeight: 300
    color: Theme.bg

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        // ================= HEADER =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 15

            Text { 
                text: "DANH SÁCH LỆNH GIAO DỊCH (TRADE LOGS)"
                color: Theme.textPrimary
                font.pixelSize: 12
                font.bold: true
            }

            Rectangle {
                width: 60
                height: 20
                color: Theme.bgCard
                border.color: Theme.border
                radius: 4
                Text {
                    anchors.centerIn: parent
                    text: "49 Lệnh"
                    color: Theme.muted
                    font.pixelSize: 10
                }
            }

            // Tabs
            RowLayout {
                spacing: 5
                Rectangle {
                    width: 50; height: 24; color: Theme.accent; radius: 4
                    Text { anchors.centerIn: parent; text: "Tất cả"; color: "#000"; font.pixelSize: 11; font.bold: true }
                }
                Text { text: "Mua (LONG)"; color: Theme.muted; font.pixelSize: 11 }
                Text { text: "Bán (SHORT)"; color: Theme.muted; font.pixelSize: 11 }
                Text { text: "Lệnh thắng"; color: Theme.muted; font.pixelSize: 11 }
                Text { text: "Lệnh thua"; color: Theme.muted; font.pixelSize: 11 }
            }

            Item { Layout.fillWidth: true } // Spacer

            // Search bar
            TextField {
                placeholderText: "Tìm theo mã lệnh, ngày..."
                color: Theme.textPrimary
                font.pixelSize: 11
                background: FieldBackground {}
                Layout.preferredWidth: 200
            }
        }

        // ================= TABLE =================
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgCard
            border.color: Theme.border
            border.width: 1
            radius: 4

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Header Row
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    color: "#1e1e24"
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        Text { text: "STT / Tên lệnh"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 150 }
                        Text { text: "Loại"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 100 }
                        Text { text: "Ngày giờ"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 150 }
                        Text { text: "Giá vào/thoát"; color: Theme.muted; font.pixelSize: 10; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                        Text { text: "Quy mô"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                        Text { text: "Lãi/Lỗ ròng"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                        Text { text: "Return"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignRight }
                    }
                }

                // Dummy List (just a visual placeholder)
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: 5
                    delegate: Rectangle {
                        width: parent.width
                        height: 40
                        color: index % 2 === 0 ? "transparent" : "#17181d"
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            
                            Text { text: "#216 vị thế mua"; color: "#4caf50"; font.pixelSize: 11; Layout.preferredWidth: 150 }
                            Text { text: "Vào\nThoát"; color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 100 }
                            Text { text: "06:00 16 thg 7, 2026\n18:00 16 thg 7, 2026"; color: Theme.textPrimary; font.pixelSize: 10; Layout.preferredWidth: 150 }
                            Text { text: "1,939.5 USD\n1,908.5 USD"; color: Theme.textPrimary; font.pixelSize: 11; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                            Text { text: "0.96 K USD\n0.5"; color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                            Text { text: "+34.66 USD"; color: "#4caf50"; font.pixelSize: 11; Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                            Text { text: "+3.61%"; color: "#4caf50"; font.pixelSize: 11; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignRight }
                        }
                    }
                }
            }
        }
    }
}
