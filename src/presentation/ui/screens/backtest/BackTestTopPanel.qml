import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

Rectangle {
    id: root
    implicitWidth: 1200
    implicitHeight: 120
    color: Theme.bg

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        // ================= ROW 1: TOOLBAR =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            // 1. Strategy ComboBox
            StrategyComboBox {
                id: strategyCombo
                model: ListModel {
                    ListElement { name: "4 EMA Pullback + Sideways Filter + QML"; category: "Market Structure & Trend" }
                    ListElement { name: "QML (Quasimodo Level) Structure Breakout"; category: "Price Action Pro" }
                    ListElement { name: "QT Smart Money Concepts (SMC + Liquidity Sweep)"; category: "Institutional Order Flow" }
                    ListElement { name: "Multi-EMA Trend Follower (EMA 8/21/50/200)"; category: "Trend Following" }
                }
                Layout.preferredWidth: 320
            }
            
            // 2. View Mode Toggle
            Rectangle {
                width: 90; implicitHeight: 32; color: "transparent"; border.color: Theme.border; radius: 4
                RowLayout {
                    anchors.fill: parent; spacing: 0
                    Button {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        background: Rectangle { color: Theme.accent; radius: 4; anchors.fill: parent; anchors.margins: 2 }
                        contentItem: Image { source: "image://icons/bar-chart-2/black"; sourceSize: Qt.size(14, 14); fillMode: Image.Pad }
                    }
                    Button {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        background: Item {}
                        contentItem: Image { source: "image://icons/activity/muted"; sourceSize: Qt.size(14, 14); fillMode: Image.Pad }
                    }
                    Button {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        background: Item {}
                        contentItem: Image { source: "image://icons/grid/muted"; sourceSize: Qt.size(14, 14); fillMode: Image.Pad }
                    }
                }
            }

            // 3. Date Picker
            Button {
                implicitHeight: 32; background: Rectangle { color: "transparent"; border.color: Theme.border; radius: 4 }
                contentItem: RowLayout {
                    spacing: 6
                    Image { source: "image://icons/calendar/muted"; sourceSize: Qt.size(14, 14) }
                    Text { text: "1 thg 1, 2025 – 11 thg 8, 2026"; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true }
                    Image { source: "image://icons/chevron-down/muted"; sourceSize: Qt.size(12, 12) }
                }
            }

            // 4. Capital
            Button {
                implicitHeight: 32; background: Rectangle { color: "transparent"; border.color: Theme.border; radius: 4 }
                contentItem: RowLayout {
                    spacing: 6
                    Text { text: "$"; color: Theme.accent; font.pixelSize: 12; font.bold: true }
                    Text { text: "1 K USD"; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true }
                    Image { source: "image://icons/chevron-down/muted"; sourceSize: Qt.size(12, 12) }
                }
            }

            // 5. Timeframe
            Button {
                implicitHeight: 32; background: Rectangle { color: "transparent"; border.color: Theme.border; radius: 4 }
                contentItem: RowLayout {
                    spacing: 6
                    Image { source: "image://icons/clock/muted"; sourceSize: Qt.size(14, 14) }
                    Text { text: "Khung thời gian: 15m"; color: Theme.muted; font.pixelSize: 11 }
                    Image { source: "image://icons/chevron-down/muted"; sourceSize: Qt.size(12, 12) }
                }
            }

            // 6. Order Execution
            Button {
                implicitHeight: 32; background: Rectangle { color: "#25262B"; border.color: Theme.border; radius: 4 }
                onClicked: orderExecMenu.open()
                contentItem: RowLayout {
                    spacing: 6
                    Image { source: "image://icons/briefcase/accent"; sourceSize: Qt.size(14, 14) }
                    Text { text: "Thực thi tập lệnh"; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true }
                    Rectangle {
                        width: 16; height: 16; radius: 8; color: Theme.accent
                        Text { anchors.centerIn: parent; text: "2"; color: "#000000"; font.pixelSize: 10; font.bold: true }
                    }
                    Image { source: "image://icons/chevron-down/muted"; sourceSize: Qt.size(12, 12) }
                }
            }

            Item { Layout.fillWidth: true }

            // Action Buttons
            Button {
                text: "Thông số Bot"
                implicitHeight: 32
                background: Rectangle { color: "transparent" }
                contentItem: Text { text: parent.text; color: Theme.accent; font.pixelSize: 12; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                onClicked: {
                    botParamsDialog.strategyIndex = strategyCombo.currentIndex
                    botParamsDialog.strategyName = strategyCombo.currentText
                    botParamsDialog.open()
                }
            }

            Button {
                text: "Chạy Backtest"
                implicitWidth: 140
                implicitHeight: 32
                background: Rectangle { color: Theme.accent; radius: 4 }
                contentItem: RowLayout {
                    spacing: 6; anchors.centerIn: parent
                    Image { source: "image://icons/play/black"; sourceSize: Qt.size(14, 14) }
                    Text { text: "Chạy Backtest"; color: "#000000"; font.pixelSize: 12; font.bold: true }
                }
            }
        }

        // ================= HEADER: PERFORMANCE METRICS =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Layout.topMargin: 10
            
            Text {
                text: "CHỈ SỐ HIỆU SUẤT BACKTEST"
                color: Theme.textPrimary
                font.pixelSize: 13
                font.bold: true
                font.letterSpacing: 1
            }
            
            RowLayout {
                spacing: 4
                Text {
                    text: "Mở rộng chỉ số chi tiết"
                    color: Theme.accent
                    font.pixelSize: 11
                }
                Image {
                    source: "image://icons/chevron-down/accent"
                    sourceSize: Qt.size(12, 12)
                }
            }
        }

        // ================= ROW 2: PERFORMANCE METRICS =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Repeater {
                model: ListModel {
                    ListElement {
                        metricTitle: "Tổng Lãi/Lỗ (Net PnL)"
                        metricValue: "-404.81"
                        metricValueColor: "#ff5252"
                        metricSuffix: "USD"
                        metricBadgeText: "-40.48%"
                        metricBadgeBgColor: "#33ff5252"
                        metricBadgeTextColor: "#ff5252"
                    }
                    ListElement {
                        metricTitle: "Mức sụt giảm tối đa (Max Drawdown)"
                        metricValue: "1,074.45"
                        metricValueColor: "#ffffff"
                        metricSuffix: "USD"
                        metricBadgeText: "-65.95%"
                        metricBadgeBgColor: "#33ff5252"
                        metricBadgeTextColor: "#ff5252"
                    }
                    ListElement {
                        metricTitle: "Tỷ lệ thắng (Win Rate)"
                        metricValue: "43.48%"
                        metricValueColor: "#4caf50"
                        metricSuffix: ""
                        metricBadgeText: "(20/46 lệnh)"
                        metricBadgeBgColor: "transparent"
                        metricBadgeTextColor: "#848E9C" // Theme.muted
                    }
                    ListElement {
                        metricTitle: "Hệ số lãi (Profit Factor)"
                        metricValue: "0.813"
                        metricValueColor: "#ff5252"
                        metricSuffix: ""
                        metricBadgeText: "Rủi ro"
                        metricBadgeBgColor: "transparent"
                        metricBadgeTextColor: "#848E9C"
                    }
                }

                MetricCard {
                    Layout.fillWidth: true
                    title: model.metricTitle
                    value: model.metricValue
                    valueColor: model.metricValueColor
                    suffix: model.metricSuffix
                    badgeText: model.metricBadgeText
                    badgeBgColor: model.metricBadgeBgColor
                    badgeTextColor: model.metricBadgeTextColor
                }
            }
        }
    }

    BotParamsDialog {
        id: botParamsDialog
    }
    
    OrderExecutionMenu {
        id: orderExecMenu
        x: 650 // Approx pos based on design, can be anchored dynamically if needed
        y: 60
    }
}
