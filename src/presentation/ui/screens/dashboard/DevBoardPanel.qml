import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// Dev Board's QML half (BOT-030 Phase 4): top bar, System Controls,
// Indicators, and the monitor log. Hosted in a QQuickWidget that sits next
// to the QtWidgets ChartCard inside a QSplitter (see dashboard_view.py) —
// ChartCard stays pyqtgraph/Widgets permanently, everything else here.
Rectangle {
    id: root

    // QQuickWidget.sizeHint() derives from these — without them the widget
    // collapses to 0x0 before QSplitter.setSizes() runs (same bug fixed for
    // the Sidebar in Phase 1).
    implicitWidth: 380
    implicitHeight: 640

    color: Theme.bg

    property bool controlsActive: (viewModel.uiMode === "IDLE" || viewModel.uiMode === "ERROR")
                                  && !viewModel.historyLoading

    component FieldBackground: Rectangle {
        color: "#17181d"
        border.color: Theme.border
        border.width: 1
        radius: 6
        implicitHeight: 32
    }

    component SectionLabel: Text {
        color: Theme.muted
        font.pixelSize: 10
        font.bold: true
        font.letterSpacing: 1
    }

    component StyledCheck: CheckBox {
        id: check
        contentItem: Text {
            leftPadding: check.indicator.width + 6
            text: check.text
            color: Theme.textPrimary
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
        }
        indicator: Rectangle {
            implicitWidth: 16
            implicitHeight: 16
            y: (check.height - height) / 2
            radius: 3
            color: check.checked ? Theme.accent : "#17181d"
            border.color: check.checked ? Theme.accent : Theme.border
            border.width: 1
        }
    }

    component PeriodSpin: SpinBox {
        id: spin
        from: 2
        to: 200
        editable: true

        contentItem: TextInput {
            text: spin.textFromValue(spin.value, spin.locale)
            color: Theme.textPrimary
            horizontalAlignment: Qt.AlignHCenter
            verticalAlignment: Qt.AlignVCenter
            readOnly: !spin.editable
            validator: spin.validator
            selectByMouse: true
            selectionColor: Theme.accent
        }

        background: FieldBackground { implicitWidth: 90 }

        up.indicator: Rectangle {
            x: spin.mirrored ? 0 : parent.width - width
            height: parent.height
            implicitWidth: 24
            color: spin.up.pressed ? "#2a2d36" : "transparent"
            Text { anchors.centerIn: parent; text: "+"; color: Theme.muted; font.pixelSize: 12 }
        }

        down.indicator: Rectangle {
            x: spin.mirrored ? parent.width - width : 0
            height: parent.height
            implicitWidth: 24
            color: spin.down.pressed ? "#2a2d36" : "transparent"
            Text { anchors.centerIn: parent; text: "−"; color: Theme.muted; font.pixelSize: 12 }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // ========================= Top bar =========================
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                objectName: "lblHeaderTitle"
                text: "Developer Board (Live Testbed)"
                color: Theme.accent
                font.pixelSize: 14
                font.bold: true
                elide: Text.ElideRight
                Layout.preferredWidth: 170
            }

            Item { Layout.fillWidth: true }

            Text {
                objectName: "lblPriceTicker"
                text: viewModel.priceTickerText
                color: viewModel.priceTickerColor
                font.pixelSize: 13
                font.bold: true
            }

            Rectangle {
                radius: 4
                color: "#17181d"
                border.color: Theme.border
                border.width: 1
                Layout.preferredWidth: wsText.implicitWidth + 16
                Layout.preferredHeight: 22
                Text {
                    id: wsText
                    objectName: "lblWsStatus"
                    anchors.centerIn: parent
                    text: viewModel.wsStatusText
                    color: viewModel.wsStatusColor
                    font.pixelSize: 10
                    font.bold: true
                }
            }

            Button {
                id: reloadButton
                objectName: "btnReload"
                text: viewModel.historyLoading ? "Loading…" : "Reload"
                enabled: root.controlsActive
                // Same action as System Controls' "Load History" button —
                // not a second code path (mirrors the QtWidgets version's
                // btn_reload.clicked.connect(load_history_button.click)).
                onClicked: viewModel.requestLoadHistory()

                contentItem: RowLayout {
                    spacing: 4
                    Image {
                        source: "image://icons/clock/muted"
                        sourceSize.width: 12
                        sourceSize.height: 12
                        Layout.preferredWidth: 12
                        Layout.preferredHeight: 12
                        opacity: reloadButton.enabled ? 1.0 : 0.4
                    }
                    Text {
                        text: reloadButton.text
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        opacity: reloadButton.enabled ? 1.0 : 0.4
                    }
                }

                background: Rectangle {
                    implicitHeight: 26
                    radius: 4
                    color: reloadButton.hovered && reloadButton.enabled ? "#1f2127" : "#17181d"
                    border.color: Theme.border
                    border.width: 1
                    opacity: reloadButton.enabled ? 1.0 : 0.5
                }
            }
        }

        // ==================== Controls + Indicators (scrollable) ====================
        ScrollView {
            id: controlsScroll
            Layout.fillWidth: true
            Layout.preferredHeight: 360
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                width: controlsScroll.width
                spacing: 14

                // ---------------- System Controls ----------------
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: controlsBody.implicitHeight + 28
                    color: Theme.bgCard
                    border.color: Theme.border
                    border.width: 1
                    radius: 8

                    ColumnLayout {
                        id: controlsBody
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        Text {
                            text: "SYSTEM CONTROLS"
                            color: Theme.accent
                            font.pixelSize: 12
                            font.bold: true
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 8

                            Text { text: "Market:"; color: Theme.textPrimary; font.pixelSize: 12 }
                            ComboBox {
                                objectName: "cboMarket"
                                Layout.fillWidth: true
                                model: ["Spot", "Futures"]
                                enabled: root.controlsActive
                                background: FieldBackground {}
                                contentItem: Text {
                                    leftPadding: 8
                                    text: parent.displayText
                                    color: Theme.textPrimary
                                    font.pixelSize: 12
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Text { text: "Symbol:"; color: Theme.textPrimary; font.pixelSize: 12 }
                            ComboBox {
                                objectName: "cboSymbol"
                                Layout.fillWidth: true
                                model: ["BTCUSDT", "ETHUSDT"]
                                editable: true
                                enabled: root.controlsActive
                                background: FieldBackground {}
                                contentItem: Text {
                                    leftPadding: 8
                                    text: parent.editText
                                    color: Theme.textPrimary
                                    font.pixelSize: 12
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Text { text: "Timeframe:"; color: Theme.textPrimary; font.pixelSize: 12 }
                            ComboBox {
                                objectName: "cboTimeframe"
                                Layout.fillWidth: true
                                model: ["1m", "5m", "15m", "1h", "1d"]
                                enabled: root.controlsActive
                                background: FieldBackground {}
                                contentItem: Text {
                                    leftPadding: 8
                                    text: parent.displayText
                                    color: Theme.textPrimary
                                    font.pixelSize: 12
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Text { text: "Strategy:"; color: Theme.textPrimary; font.pixelSize: 12 }
                            ComboBox {
                                objectName: "cboStrategy"
                                Layout.fillWidth: true
                                model: ["Manual", "SMA Crossover"]
                                enabled: root.controlsActive
                                background: FieldBackground {}
                                contentItem: Text {
                                    leftPadding: 8
                                    text: parent.displayText
                                    color: Theme.textPrimary
                                    font.pixelSize: 12
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        SectionLabel { text: "DATA RANGE" }

                        // Plain text fields, not a calendar popup — Qt Quick
                        // Controls Basic has no date-time editor (same call
                        // as DatabaseScreen.qml). Cosmetic only, like the
                        // QDateTimeEdit pair they replace: Load History
                        // always uses a fixed limit, never reads these (see
                        // dev_board_user_end_test_cases.md TC-GAP-04/05).
                        TextField {
                            objectName: "txtStartDate"
                            Layout.fillWidth: true
                            text: Qt.formatDateTime(new Date(Date.now() - 7 * 86400000), "yyyy-MM-dd HH:mm")
                            enabled: root.controlsActive
                            color: Theme.textPrimary
                            font.pixelSize: 12
                            background: FieldBackground {}
                        }
                        TextField {
                            objectName: "txtEndDate"
                            Layout.fillWidth: true
                            text: Qt.formatDateTime(new Date(), "yyyy-MM-dd HH:mm")
                            enabled: root.controlsActive
                            color: Theme.textPrimary
                            font.pixelSize: 12
                            background: FieldBackground {}
                        }

                        SectionLabel { text: "ACTIONS" }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Button {
                                id: loadButton
                                objectName: "btnLoadHistory"
                                Layout.fillWidth: true
                                text: viewModel.historyLoading ? "Loading…" : "Load History"
                                enabled: root.controlsActive
                                onClicked: viewModel.requestLoadHistory()

                                contentItem: RowLayout {
                                    spacing: 5
                                    Image {
                                        source: "image://icons/clock/muted"
                                        sourceSize.width: 13
                                        sourceSize.height: 13
                                        Layout.preferredWidth: 13
                                        Layout.preferredHeight: 13
                                        opacity: loadButton.enabled ? 1.0 : 0.4
                                    }
                                    Text {
                                        text: loadButton.text
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        opacity: loadButton.enabled ? 1.0 : 0.4
                                    }
                                }

                                background: Rectangle {
                                    implicitHeight: 32
                                    radius: 6
                                    color: loadButton.hovered && loadButton.enabled ? "#1f2127" : "#17181d"
                                    border.color: Theme.border
                                    border.width: 1
                                    opacity: loadButton.enabled ? 1.0 : 0.5
                                }
                            }

                            Button {
                                id: startButton
                                objectName: "btnStart"
                                Layout.fillWidth: true
                                text: "Start Live"
                                enabled: root.controlsActive
                                onClicked: viewModel.requestStartStream()

                                contentItem: RowLayout {
                                    spacing: 5
                                    Image {
                                        source: "image://icons/play/success"
                                        sourceSize.width: 13
                                        sourceSize.height: 13
                                        Layout.preferredWidth: 13
                                        Layout.preferredHeight: 13
                                        opacity: startButton.enabled ? 1.0 : 0.4
                                    }
                                    Text {
                                        text: startButton.text
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        opacity: startButton.enabled ? 1.0 : 0.4
                                    }
                                }

                                background: Rectangle {
                                    implicitHeight: 32
                                    radius: 6
                                    color: startButton.hovered && startButton.enabled ? "#1f2127" : "#17181d"
                                    border.color: Theme.success
                                    border.width: 1
                                    opacity: startButton.enabled ? 1.0 : 0.5
                                }
                            }

                            Button {
                                id: stopButton
                                objectName: "btnStop"
                                Layout.fillWidth: true
                                text: "Stop"
                                enabled: viewModel.uiMode === "LIVE"
                                onClicked: viewModel.requestStopStream()

                                contentItem: RowLayout {
                                    spacing: 5
                                    Image {
                                        source: "image://icons/square/danger"
                                        sourceSize.width: 13
                                        sourceSize.height: 13
                                        Layout.preferredWidth: 13
                                        Layout.preferredHeight: 13
                                        opacity: stopButton.enabled ? 1.0 : 0.4
                                    }
                                    Text {
                                        text: stopButton.text
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        opacity: stopButton.enabled ? 1.0 : 0.4
                                    }
                                }

                                background: Rectangle {
                                    implicitHeight: 32
                                    radius: 6
                                    color: stopButton.hovered && stopButton.enabled ? "#1f2127" : "#17181d"
                                    border.color: Theme.danger
                                    border.width: 1
                                    opacity: stopButton.enabled ? 1.0 : 0.5
                                }
                            }
                        }
                    }
                }

                // ---------------- Indicators ----------------
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: indicatorsBody.implicitHeight + 28
                    color: Theme.bgCard
                    border.color: Theme.border
                    border.width: 1
                    radius: 8

                    ColumnLayout {
                        id: indicatorsBody
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        Text {
                            text: "INDICATORS"
                            color: Theme.accent
                            font.pixelSize: 12
                            font.bold: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            StyledCheck {
                                objectName: "chkRsi"
                                text: "RSI"
                                checked: viewModel.rsiEnabled
                                onToggled: viewModel.rsiEnabled = checked
                            }
                            Text { text: "Period:"; color: Theme.muted; font.pixelSize: 11 }
                            PeriodSpin {
                                objectName: "spinRsiPeriod"
                                value: viewModel.rsiPeriod
                                onValueModified: viewModel.rsiPeriod = value
                            }
                            Item { Layout.fillWidth: true }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            StyledCheck {
                                objectName: "chkEma"
                                text: "EMA"
                                checked: viewModel.emaEnabled
                                onToggled: viewModel.emaEnabled = checked
                            }
                            Text { text: "Period:"; color: Theme.muted; font.pixelSize: 11 }
                            PeriodSpin {
                                objectName: "spinEmaPeriod"
                                value: viewModel.emaPeriod
                                onValueModified: viewModel.emaPeriod = value
                            }
                            Item { Layout.fillWidth: true }
                        }

                        StyledCheck {
                            objectName: "chkMacd"
                            text: "MACD (12/26/9)"
                            checked: viewModel.macdEnabled
                            onToggled: viewModel.macdEnabled = checked
                        }
                    }
                }
            }
        }

        // ========================= Monitor log =========================
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
