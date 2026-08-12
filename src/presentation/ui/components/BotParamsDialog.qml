import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

Popup {
    id: root
    width: 650
    height: 500
    modal: true
    dim: true
    anchors.centerIn: Overlay.overlay

    // Pass the currently selected strategy index and name from the parent
    property int strategyIndex: 0
    property string strategyName: "4 EMA PULLBACK + SIDEWAYS FILTER + QML"

    background: Rectangle {
        color: Theme.bg
        border.color: Theme.border
        border.width: 1
        radius: 6
    }

    // Title Bar
    Rectangle {
        id: titleBar
        width: parent.width
        height: 45
        color: "transparent"
        
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 15
            anchors.rightMargin: 15
            
            Image {
                source: "image://icons/sliders/accent"
                sourceSize: Qt.size(16, 16)
            }
            Text {
                text: "CẤU HÌNH THÔNG SỐ BOT: " + root.strategyName.toUpperCase()
                color: Theme.textPrimary
                font.pixelSize: 12
                font.bold: true
                Layout.fillWidth: true
            }
            
            // Close Button
            MouseArea {
                implicitWidth: 20
                implicitHeight: 20
                cursorShape: Qt.PointingHandCursor
                onClicked: root.close()
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: Theme.muted
                    font.pixelSize: 14
                }
            }
        }
        
        // Divider
        Rectangle {
            width: parent.width
            height: 1
            color: Theme.border
            anchors.bottom: parent.bottom
        }
    }

    // Body (Dynamic Content)
    ScrollView {
        width: parent.width
        anchors.top: titleBar.bottom
        anchors.bottom: footer.top
        anchors.margins: 15
        clip: true

        StackLayout {
            width: parent.width
            currentIndex: root.strategyIndex

            // ================== STRATEGY 0: 4 EMA PULLBACK ==================
            ColumnLayout {
                spacing: 15
                Layout.fillWidth: true

                // Section 1: Risk & Leverage
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 140
                    color: "transparent"
                    border.color: Theme.border
                    radius: 4
                    
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10
                        
                        RowLayout {
                            Image { source: "image://icons/shield/accent"; sourceSize: Qt.size(14, 14) }
                            Text { text: "Quản lý Rủi ro & Đòn bẩy (Risk & Leverage)"; color: Theme.textPrimary; font.pixelSize: 12; font.bold: true }
                        }
                        
                        GridLayout {
                            columns: 2
                            columnSpacing: 20
                            rowSpacing: 10
                            Layout.fillWidth: true
                            
                            // SL
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Stop Loss (SL %)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "1.2"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            // TP
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Take Profit (TP %)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "3.2"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            // Leverage
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Đòn bẩy (Leverage)"; color: Theme.muted; font.pixelSize: 11 }
                                ComboBox { 
                                    model: ["1x Spot", "5x Futures", "10x Futures"]
                                    currentIndex: 1
                                    background: FieldBackground {}
                                    contentItem: Text { leftPadding: 8; text: parent.displayText; color: Theme.textPrimary; verticalAlignment: Text.AlignVCenter; font.pixelSize: 12 }
                                    Layout.fillWidth: true 
                                }
                            }
                            // Risk
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Rủi ro mỗi lệnh (% Vốn)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "2"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }

                // Section 2: Technicals
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 110
                    color: "transparent"
                    border.color: Theme.border
                    radius: 4
                    
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10
                        
                        RowLayout {
                            Image { source: "image://icons/zap/accent"; sourceSize: Qt.size(14, 14) }
                            Text { text: "Chỉ số Kỹ thuật & Độ nhạy QML"; color: Theme.textPrimary; font.pixelSize: 12; font.bold: true }
                        }
                        
                        GridLayout {
                            columns: 2
                            columnSpacing: 20
                            rowSpacing: 10
                            Layout.fillWidth: true
                            
                            // EMA
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "EMA Fast / Slow"; color: Theme.muted; font.pixelSize: 11 }
                                RowLayout {
                                    TextField {
                                        text: "8"
                                        color: Theme.textPrimary
                                        background: FieldBackground {}
                                        Layout.fillWidth: true
                                    }
                                    TextField {
                                        text: "21"
                                        color: Theme.textPrimary
                                        background: FieldBackground {}
                                        Layout.fillWidth: true
                                    }
                                }
                            }
                            // Score
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Độ nhạy Mẫu hình QML (Score %)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "85"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }

            // ================== STRATEGY 1: QML STRUCTURE BREAKOUT ==================
            ColumnLayout {
                spacing: 15
                Layout.fillWidth: true

                // Section 1: Risk & Leverage
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 140
                    color: "transparent"
                    border.color: Theme.border
                    radius: 4
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10
                        RowLayout {
                            Image { source: "image://icons/shield/accent"; sourceSize: Qt.size(14, 14) }
                            Text { text: "Quản lý Rủi ro"; color: Theme.textPrimary; font.pixelSize: 12; font.bold: true }
                        }
                        GridLayout {
                            columns: 2
                            columnSpacing: 20
                            rowSpacing: 10
                            Layout.fillWidth: true
                            
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Stop Loss (SL %)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "2.0"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Take Profit (TP %)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "6.0"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Đòn bẩy"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "3x Futures"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Risk per Trade"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "1.5"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }

                // Section 2: Smart Money Concepts Params
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 110
                    color: "transparent"
                    border.color: Theme.border
                    radius: 4
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10
                        RowLayout {
                            Image { source: "image://icons/zap/accent"; sourceSize: Qt.size(14, 14) }
                            Text { text: "Quasimodo Pattern Settings"; color: Theme.textPrimary; font.pixelSize: 12; font.bold: true }
                        }
                        GridLayout {
                            columns: 2
                            columnSpacing: 20
                            rowSpacing: 10
                            Layout.fillWidth: true
                            
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Left Shoulder Tolerance (%)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "0.5"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Minimum RR required"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "3.0"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }

            // ================== STRATEGY 2: QT SMART MONEY CONCEPTS ==================
            ColumnLayout {
                spacing: 15
                Layout.fillWidth: true

                // Section 1: Risk & Leverage
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 140
                    color: "transparent"
                    border.color: Theme.border
                    radius: 4
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10
                        RowLayout {
                            Image { source: "image://icons/shield/accent"; sourceSize: Qt.size(14, 14) }
                            Text { text: "Quản lý Rủi ro"; color: Theme.textPrimary; font.pixelSize: 12; font.bold: true }
                        }
                        GridLayout {
                            columns: 2
                            columnSpacing: 20
                            rowSpacing: 10
                            Layout.fillWidth: true
                            
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Stop Loss (SL %)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "1.0"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Take Profit (TP %)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "5.0"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Đòn bẩy"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "10x Futures"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Risk per Trade"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "3"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }

                // Section 2: FVG and Liquidity Params
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 110
                    color: "transparent"
                    border.color: Theme.border
                    radius: 4
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10
                        RowLayout {
                            Image { source: "image://icons/zap/accent"; sourceSize: Qt.size(14, 14) }
                            Text { text: "Fair Value Gap & Liquidity"; color: Theme.textPrimary; font.pixelSize: 12; font.bold: true }
                        }
                        GridLayout {
                            columns: 2
                            columnSpacing: 20
                            rowSpacing: 10
                            Layout.fillWidth: true
                            
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "FVG Mitigation Thresh (%)"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "50"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text { text: "Liquidity Sweep Candles"; color: Theme.muted; font.pixelSize: 11 }
                                TextField {
                                    text: "10"
                                    color: Theme.textPrimary
                                    background: FieldBackground {}
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }

            // Fallback for Strategy 3 (Trend Follower)
            ColumnLayout {
                Text { text: "Parameters for Multi-EMA Trend Follower..."; color: Theme.textPrimary }
            }
        }
    }

    // Footer
    Rectangle {
        id: footer
        width: parent.width
        height: 60
        color: "transparent"
        anchors.bottom: parent.bottom
        
        // Top divider
        Rectangle { width: parent.width; height: 1; color: Theme.border; anchors.top: parent.top }
        
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 15
            anchors.rightMargin: 15
            
            // Left action
            MouseArea {
                implicitWidth: restoreLayout.implicitWidth
                implicitHeight: 30
                cursorShape: Qt.PointingHandCursor
                RowLayout {
                    id: restoreLayout
                    anchors.centerIn: parent
                    spacing: 5
                    Image { source: "image://icons/rotate-ccw/muted"; sourceSize: Qt.size(14, 14) }
                    Text { text: "Khôi phục Mặc định"; color: Theme.muted; font.pixelSize: 12 }
                }
            }
            
            Item { Layout.fillWidth: true }
            
            // Right actions
            Button {
                text: "Hủy"
                background: Rectangle { color: "#2b2d35"; radius: 4 }
                contentItem: Text { text: parent.text; color: Theme.textPrimary; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                implicitWidth: 80
                implicitHeight: 32
                onClicked: root.close()
            }
            
            Button {
                text: "Lưu & Re-Backtest"
                background: Rectangle { color: Theme.accent; radius: 4 }
                contentItem: RowLayout {
                    spacing: 5
                    Image { source: "image://icons/save/black"; sourceSize: Qt.size(14, 14) }
                    Text { text: parent.parent.text; color: "#000000"; font.pixelSize: 12; font.bold: true }
                }
                implicitWidth: 160
                implicitHeight: 32
                onClicked: root.close()
            }
        }
    }
}
