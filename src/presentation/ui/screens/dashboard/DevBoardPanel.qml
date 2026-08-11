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
                                id: symbolCombo
                                objectName: "cboSymbol"
                                Layout.fillWidth: true
                                property var presetSymbols: ["BTCUSDT", "ETHUSDT"]
                                // Guards onCurrentTextChanged below until this
                                // ComboBox's OWN initial currentIndex (0, the
                                // Qt-assigned default the instant `model` is set,
                                // firing currentTextChanged with "BTCUSDT" before
                                // Component.onCompleted below ever runs) has been
                                // corrected to the real default from
                                // viewModel.symbol ("ETHUSDT") — without this guard
                                // that transient default silently overwrites the
                                // ViewModel's real default the moment the screen
                                // opens (reproduced: presenter._active_symbol ends
                                // up "BTCUSDT" instead of "ETHUSDT" at construction,
                                // caught by test_script_lines_are_routed_to_the_runner
                                // and its siblings, not a hypothetical).
                                property bool _initialSyncDone: false
                                model: presetSymbols
                                editable: true
                                enabled: root.controlsActive
                                // One-time initial selection, NOT a live binding to
                                // viewModel.symbol: this field accepts free-typed
                                // symbols outside presetSymbols (e.g. "SOLUSDT"), and
                                // a live `currentIndex: Math.max(0, presetSymbols.indexOf(viewModel.symbol))`
                                // binding would re-evaluate on every keystroke's
                                // onCurrentTextChanged write-back, see indexOf return
                                // -1 for anything not in the 2-item preset list, and
                                // snap currentIndex back to 0 — silently overwriting
                                // whatever the user just typed with "BTCUSDT" (a real,
                                // reproduced binding-loop bug caught by
                                // test_on_load_history_rejects_an_invalid_symbol during
                                // this task, not a hypothetical).
                                Component.onCompleted: {
                                    currentIndex = Math.max(0, presetSymbols.indexOf(viewModel.symbol))
                                    _initialSyncDone = true
                                }
                                onCurrentTextChanged: if (_initialSyncDone) viewModel.symbol = currentText
                                background: FieldBackground {}
                                contentItem: Text {
                                    leftPadding: 8
                                    text: parent.editText
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
                        // as DatabaseScreen.qml). BOT-033 Phase 2: bound to
                        // viewModel.startDate/endDate, read+validated by
                        // DashboardPresenter at Load History/Start Live
                        // click time (see stream_lifecycle_controller.py).
                        // onTextEdited (not onTextChanged) fires only on
                        // user edits, matching DatabaseScreen.qml's
                        // txtFromDateTime/txtToDateTime — a programmatic
                        // `text:` update from the ViewModel must not loop
                        // back into the ViewModel it came from.
                        TextField {
                            objectName: "txtStartDate"
                            Layout.fillWidth: true
                            text: viewModel.startDate
                            onTextEdited: viewModel.startDate = text
                            placeholderText: "yyyy-MM-dd HH:mm"
                            enabled: root.controlsActive
                            color: Theme.textPrimary
                            font.pixelSize: 12
                            background: FieldBackground {}
                        }
                        TextField {
                            objectName: "txtEndDate"
                            Layout.fillWidth: true
                            text: viewModel.endDate
                            onTextEdited: viewModel.endDate = text
                            placeholderText: "yyyy-MM-dd HH:mm"
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

                        // BOT-032 Phase 6 — every indicator is a script, none
                        // hardcoded here anymore. Populated at runtime from
                        // IndicatorScriptRegistry via viewModel.scriptModel —
                        // a new registered script appears with no QML change.
                        // RSI(14)/EMA 20/50/100/200/MACD(12/26/9) are the
                        // built-in defaults (see binance_bot_module.py); the
                        // EMA ones start pre-checked (default_enabled).
                        Repeater {
                            id: scriptRepeater
                            model: viewModel.scriptModel

                            RowLayout {
                                Layout.fillWidth: true
                                required property var model
                                required property int index

                                StyledCheck {
                                    objectName: "chkScript_" + parent.model.key
                                    text: parent.model.title
                                    checked: parent.model.enabled
                                    onToggled: viewModel.scriptModel.setEnabled(parent.index, checked)
                                }
                                Item { Layout.fillWidth: true }
                            }
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
