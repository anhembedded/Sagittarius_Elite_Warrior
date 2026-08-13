import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

Rectangle {
    id: root

    implicitWidth: 380
    implicitHeight: 640

    color: "#0d0e14"

    property bool controlsActive: viewModel.controlsEnabled && !viewModel.historyLoading

    component SectionLabel: RowLayout {
        property string titleText: ""
        spacing: 6
        Rectangle {
            width: 3
            height: 12
            color: Theme.accent
            radius: 1.5
        }
        Text {
            text: titleText.toUpperCase()
            color: Theme.muted
            font.pixelSize: 10
            font.bold: true
            font.letterSpacing: 0.8
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        // ========================= Top Header Bar =========================
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 44
            color: "#12141d"
            border.color: "#222533"
            border.width: 1
            radius: 8

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 10

                RowLayout {
                    spacing: 6
                    Rectangle {
                        width: 3
                        height: 14
                        color: Theme.accent
                        radius: 2
                    }
                    Text {
                        objectName: "lblHeaderTitle"
                        text: "Developer Board (Live Testbed)"
                        color: Theme.textPrimary
                        font.pixelSize: 13
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.preferredWidth: 170
                    }
                }

                Item { Layout.fillWidth: true }

                Text {
                    objectName: "lblPriceTicker"
                    text: viewModel.priceTickerText
                    color: viewModel.priceTickerColor
                    font.pixelSize: 13
                    font.bold: true
                    font.family: "Inter, Segoe UI, sans-serif"
                }

                Rectangle {
                    radius: 11
                    color: "#181a26"
                    border.color: "#282b3d"
                    border.width: 1
                    Layout.preferredWidth: wsText.implicitWidth + 20
                    Layout.preferredHeight: 22

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 6
                        Rectangle {
                            width: 6
                            height: 6
                            radius: 3
                            color: viewModel.wsStatusColor
                        }
                        Text {
                            id: wsText
                            objectName: "lblWsStatus"
                            text: viewModel.wsStatusText
                            color: viewModel.wsStatusColor
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                }

                StatefulButton {
                    objectName: "btnReload"
                    text: viewModel.historyLoading ? "Loading…" : "Reload"
                    enabled: root.controlsActive
                    iconSource: "clock"
                    iconSize: 12
                    implicitHeight: 26
                    onClicked: viewModel.requestLoadHistory()
                }
            }
        }

        // ==================== Controls + Indicators (scrollable) ====================
        ScrollView {
            id: controlsScroll
            Layout.fillWidth: true
            Layout.preferredHeight: 380
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                width: controlsScroll.width
                spacing: 12

                // ---------------- System Controls Card ----------------
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: controlsBody.implicitHeight + 28
                    color: "#12141d"
                    border.color: "#222533"
                    border.width: 1
                    radius: 8

                    ColumnLayout {
                        id: controlsBody
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 12

                        SectionLabel { titleText: "System Controls" }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 10
                            rowSpacing: 10

                            Text { text: "Market:"; color: Theme.muted; font.pixelSize: 11; font.bold: true }
                            ComboBox {
                                objectName: "cboMarket"
                                Layout.fillWidth: true
                                implicitHeight: 32
                                model: ["Spot", "Futures"]
                                enabled: root.controlsActive
                                background: Rectangle {
                                    color: "#181a24"
                                    border.color: "#2a2d3d"
                                    border.width: 1
                                    radius: 6
                                }
                                contentItem: Text {
                                    leftPadding: 10
                                    text: parent.displayText
                                    color: Theme.textPrimary
                                    font.pixelSize: 11
                                    font.bold: true
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Text { text: "Symbol:"; color: Theme.muted; font.pixelSize: 11; font.bold: true }
                            ComboBox {
                                id: symbolCombo
                                objectName: "cboSymbol"
                                Layout.fillWidth: true
                                implicitHeight: 32
                                property var presetSymbols: ["BTCUSDT", "ETHUSDT"]
                                property bool _initialSyncDone: false
                                model: presetSymbols
                                editable: true
                                enabled: root.controlsActive
                                Component.onCompleted: {
                                    currentIndex = Math.max(0, presetSymbols.indexOf(viewModel.symbol))
                                    _initialSyncDone = true
                                }
                                onCurrentTextChanged: if (_initialSyncDone) viewModel.symbol = currentText
                                background: Rectangle {
                                    color: "#181a24"
                                    border.color: "#2a2d3d"
                                    border.width: 1
                                    radius: 6
                                }
                                contentItem: Text {
                                    leftPadding: 10
                                    text: parent.editText
                                    color: Theme.textPrimary
                                    font.pixelSize: 11
                                    font.bold: true
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Text { text: "Strategy:"; color: Theme.muted; font.pixelSize: 11; font.bold: true }
                            ComboBox {
                                objectName: "cboStrategy"
                                Layout.fillWidth: true
                                implicitHeight: 32
                                model: ["Manual", "SMA Crossover"]
                                enabled: root.controlsActive
                                background: Rectangle {
                                    color: "#181a24"
                                    border.color: "#2a2d3d"
                                    border.width: 1
                                    radius: 6
                                }
                                contentItem: Text {
                                    leftPadding: 10
                                    text: parent.displayText
                                    color: Theme.textPrimary
                                    font.pixelSize: 11
                                    font.bold: true
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        SectionLabel { titleText: "Data Range" }

                        TextField {
                            objectName: "txtStartDate"
                            Layout.fillWidth: true
                            implicitHeight: 32
                            text: viewModel.startDate
                            onTextEdited: viewModel.startDate = text
                            placeholderText: "yyyy-MM-dd HH:mm"
                            enabled: root.controlsActive
                            color: Theme.textPrimary
                            font.pixelSize: 11
                            background: Rectangle {
                                color: "#181a24"
                                border.color: "#2a2d3d"
                                border.width: 1
                                radius: 6
                            }
                        }
                        TextField {
                            objectName: "txtEndDate"
                            Layout.fillWidth: true
                            implicitHeight: 32
                            text: viewModel.endDate
                            onTextEdited: viewModel.endDate = text
                            placeholderText: "yyyy-MM-dd HH:mm"
                            enabled: root.controlsActive
                            color: Theme.textPrimary
                            font.pixelSize: 11
                            background: Rectangle {
                                color: "#181a24"
                                border.color: "#2a2d3d"
                                border.width: 1
                                radius: 6
                            }
                        }

                        SectionLabel { titleText: "Actions" }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            StatefulButton {
                                objectName: "btnLoadHistory"
                                Layout.fillWidth: true
                                text: viewModel.historyLoading ? "Loading…" : "Load History"
                                enabled: root.controlsActive
                                iconSource: "clock"
                                iconTint: "muted"
                                onClicked: viewModel.requestLoadHistory()
                            }

                            StatefulButton {
                                objectName: "btnStart"
                                Layout.fillWidth: true
                                text: "Start Live"
                                enabled: root.controlsActive
                                iconSource: "play"
                                iconTint: "success"
                                accentBorder: Theme.success
                                onClicked: viewModel.requestStartStream()
                            }

                            StatefulButton {
                                objectName: "btnStop"
                                Layout.fillWidth: true
                                text: "Stop"
                                enabled: viewModel.uiMode === "LIVE"
                                iconSource: "square"
                                iconTint: "danger"
                                accentBorder: Theme.danger
                                onClicked: viewModel.requestStopStream()
                            }
                        }
                    }
                }

                // ---------------- Indicators Card ----------------
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: indicatorsBody.implicitHeight + 28
                    color: "#12141d"
                    border.color: "#222533"
                    border.width: 1
                    radius: 8

                    ColumnLayout {
                        id: indicatorsBody
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        SectionLabel { titleText: "Indicators" }

                        Repeater {
                            id: scriptRepeater
                            model: viewModel.scriptModel

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 32
                                color: checkMouse.containsMouse ? "#181b27" : "transparent"
                                radius: 6

                                MouseArea {
                                    id: checkMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: viewModel.scriptModel.setEnabled(index, !modelData.enabled)
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8

                                    StyledCheck {
                                        objectName: "chkScript_" + modelData.key
                                        text: modelData.title
                                        checked: modelData.enabled
                                        onToggled: viewModel.scriptModel.setEnabled(index, checked)
                                    }
                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ========================= System Monitor Log Panel =========================
        LogPanel {
            objectName: "monitorLogPanel"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 160
            title: "SYSTEM MONITOR"
            logModel: viewModel.logModel
        }
    }
}

