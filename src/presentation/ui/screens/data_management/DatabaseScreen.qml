import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// Database screen (BOT-030 Phase 3). Folds in the visual design BOT-029
// Phase 3 planned for QtWidgets (stat tiles, search, placeholder actions)
// rather than building it twice.
Rectangle {
    id: root

    color: Theme.bg

    // Shared field styling — every input on this screen looks the same, so
    // the recipe lives in one place instead of being repeated per control.
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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14

        // ================= Header + placeholder actions ================
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Image {
                source: "image://icons/database/accent"
                sourceSize.width: 22
                sourceSize.height: 22
                Layout.preferredWidth: 22
                Layout.preferredHeight: 22
            }

            ColumnLayout {
                spacing: 0
                Text {
                    text: "SAGITTARIUS STORAGE VAULT"
                    color: Theme.accent
                    font.pixelSize: 15
                    font.bold: true
                }
                Text {
                    text: "Historical Market KLines Database"
                    color: Theme.muted
                    font.pixelSize: 11
                }
            }

            Item { Layout.fillWidth: true }

            // Rendered but disabled: no seeding/export/purge logic exists.
            // Shown for layout parity with the mock without pretending to
            // work — clicking must never look like it did something.
            Repeater {
                model: [
                    { label: "Seed Records", icon: "database" },
                    { label: "Export JSON", icon: "clock" },
                    { label: "Purge Vault", icon: "trash-2" }
                ]

                Button {
                    id: placeholderButton
                    required property var modelData
                    objectName: "btnPlaceholder_" + modelData.label.replace(" ", "_")
                    text: modelData.label
                    enabled: false
                    ToolTip.visible: hovered
                    ToolTip.text: "Not implemented yet"

                    contentItem: RowLayout {
                        spacing: 5
                        Image {
                            source: "image://icons/" + placeholderButton.modelData.icon + "/muted"
                            sourceSize.width: 13
                            sourceSize.height: 13
                            Layout.preferredWidth: 13
                            Layout.preferredHeight: 13
                        }
                        Text {
                            text: placeholderButton.text
                            color: Theme.muted
                            font.pixelSize: 11
                        }
                    }
                    background: Rectangle {
                        implicitHeight: 30
                        implicitWidth: 118
                        radius: 6
                        color: "#131418"
                        border.color: Theme.border
                        border.width: 1
                        opacity: 0.6
                    }
                }
            }
        }

        // ========================= Stat tiles =========================
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Repeater {
                model: [
                    { label: "Stored KLines Records", value: viewModel.storedRecords,
                      hint: "across scanned symbol/interval pairs" },
                    { label: "Est. Database Size", value: viewModel.databaseSize,
                      hint: "on-disk SQLite file (WAL mode)" }
                ]

                Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 74
                    color: Theme.bgCard
                    border.color: Theme.border
                    border.width: 1
                    radius: 8

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 2
                        Text {
                            text: parent.parent.modelData.label
                            color: Theme.muted
                            font.pixelSize: 11
                        }
                        Text {
                            objectName: "statValue_" + parent.parent.modelData.label
                            text: parent.parent.modelData.value
                            color: "#ffffff"
                            font.pixelSize: 18
                            font.bold: true
                        }
                        Text {
                            text: parent.parent.modelData.hint
                            color: Theme.muted
                            font.pixelSize: 9
                        }
                    }
                }
            }
        }

        // ================== Controls + table/log split =================
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            // ---------------- Sync controls -------------------------
            Rectangle {
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                color: Theme.bgCard
                border.color: Theme.border
                border.width: 1
                radius: 8

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Text {
                        text: "SYNC CONTROLS"
                        color: Theme.accent
                        font.pixelSize: 12
                        font.bold: true
                    }

                    SectionLabel { text: "TARGET" }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 8
                        rowSpacing: 8

                        Text { text: "Symbol:"; color: Theme.textPrimary; font.pixelSize: 12 }
                        ComboBox {
                            objectName: "cboSymbol"
                            Layout.fillWidth: true
                            model: viewModel.symbols
                            editable: true
                            enabled: viewModel.uiMode !== "LOCKED"
                            currentIndex: Math.max(0, viewModel.symbols.indexOf(viewModel.selectedSymbol))
                            onCurrentTextChanged: viewModel.selectedSymbol = currentText
                            background: FieldBackground {}
                            contentItem: Text {
                                leftPadding: 8
                                text: parent.editText
                                color: Theme.textPrimary
                                font.pixelSize: 12
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Text { text: "Interval:"; color: Theme.textPrimary; font.pixelSize: 12 }
                        ComboBox {
                            objectName: "cboInterval"
                            Layout.fillWidth: true
                            model: viewModel.intervals
                            enabled: viewModel.uiMode !== "LOCKED"
                            currentIndex: Math.max(0, viewModel.intervals.indexOf(viewModel.selectedInterval))
                            onCurrentTextChanged: viewModel.selectedInterval = currentText
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

                    SectionLabel { text: "TIME RANGE" }

                    CheckBox {
                        id: customTimeCheck
                        objectName: "chkCustomTime"
                        text: "Use Custom Time Range"
                        checked: viewModel.useCustomTime
                        enabled: viewModel.uiMode !== "LOCKED"
                        onToggled: viewModel.useCustomTime = checked
                        contentItem: Text {
                            leftPadding: customTimeCheck.indicator.width + 6
                            text: customTimeCheck.text
                            color: Theme.textPrimary
                            font.pixelSize: 12
                            verticalAlignment: Text.AlignVCenter
                        }
                        indicator: Rectangle {
                            implicitWidth: 16
                            implicitHeight: 16
                            y: (customTimeCheck.height - height) / 2
                            radius: 3
                            color: customTimeCheck.checked ? Theme.accent : "#17181d"
                            border.color: customTimeCheck.checked ? Theme.accent : Theme.border
                            border.width: 1
                        }
                    }

                    // Plain text fields rather than a calendar popup: Qt Quick
                    // Controls Basic has no date-time editor, and inventing one
                    // is out of scope for this migration. Format is stated in
                    // the placeholder so the expected input is unambiguous.
                    TextField {
                        objectName: "txtFromDateTime"
                        Layout.fillWidth: true
                        enabled: viewModel.useCustomTime && viewModel.uiMode !== "LOCKED"
                        text: viewModel.fromDateTime
                        onTextEdited: viewModel.fromDateTime = text
                        placeholderText: "From  yyyy-MM-dd HH:mm"
                        color: Theme.textPrimary
                        font.pixelSize: 12
                        background: FieldBackground {}
                    }

                    TextField {
                        objectName: "txtToDateTime"
                        Layout.fillWidth: true
                        enabled: viewModel.useCustomTime && viewModel.uiMode !== "LOCKED"
                        text: viewModel.toDateTime
                        onTextEdited: viewModel.toDateTime = text
                        placeholderText: "To  yyyy-MM-dd HH:mm"
                        color: Theme.textPrimary
                        font.pixelSize: 12
                        background: FieldBackground {}
                    }

                    SectionLabel { text: "ACTIONS" }

                    // One declarative table drives every action button, so a
                    // new action is a row here rather than another copy of
                    // the same 20 lines of styling.
                    Repeater {
                        model: [
                            { name: "btnCheckStatus", label: "Scan Current Status",
                              icon: "database", tint: "muted", action: "checkStatus" },
                            { name: "btnCheckAll", label: "Scan All Status",
                              icon: "layout-dashboard", tint: "muted", action: "checkAll" },
                            { name: "btnSyncData", label: "Sync Current",
                              icon: "play", tint: "success", action: "sync" },
                            { name: "btnSyncAllGaps", label: "Sync All Gaps",
                              icon: "clock", tint: "success", action: "syncAllGaps" },
                            { name: "btnClearData", label: "Clear Local Data",
                              icon: "trash-2", tint: "danger", action: "clearData" }
                        ]

                        Button {
                            id: actionButton
                            required property var modelData
                            objectName: modelData.name
                            text: modelData.label
                            Layout.fillWidth: true
                            enabled: viewModel.uiMode !== "LOCKED"

                            onClicked: {
                                switch (modelData.action) {
                                case "checkStatus": viewModel.requestCheckStatus(); break;
                                case "checkAll": viewModel.requestCheckAllStatus(); break;
                                case "sync": viewModel.requestSync(); break;
                                case "syncAllGaps": viewModel.requestSyncAllGaps(); break;
                                case "clearData": viewModel.requestClearData(); break;
                                }
                            }

                            contentItem: RowLayout {
                                spacing: 6
                                Image {
                                    source: "image://icons/" + actionButton.modelData.icon
                                            + "/" + actionButton.modelData.tint
                                    sourceSize.width: 14
                                    sourceSize.height: 14
                                    Layout.preferredWidth: 14
                                    Layout.preferredHeight: 14
                                    opacity: actionButton.enabled ? 1.0 : 0.4
                                }
                                Text {
                                    text: actionButton.text
                                    color: Theme.textPrimary
                                    font.pixelSize: 12
                                    opacity: actionButton.enabled ? 1.0 : 0.4
                                    Layout.fillWidth: true
                                }
                            }

                            background: Rectangle {
                                implicitHeight: 32
                                radius: 6
                                color: actionButton.hovered && actionButton.enabled
                                       ? "#1f2127" : "#17181d"
                                border.width: 1
                                border.color: actionButton.modelData.tint === "danger"
                                              ? Theme.danger
                                              : (actionButton.modelData.tint === "success"
                                                 ? Theme.success : Theme.border)
                                opacity: actionButton.enabled ? 1.0 : 0.5
                            }
                        }
                    }

                    ProgressBar {
                        objectName: "syncProgress"
                        Layout.fillWidth: true
                        visible: viewModel.progressVisible
                        indeterminate: viewModel.progressMaximum === 0
                        from: 0
                        to: Math.max(1, viewModel.progressMaximum)
                        value: viewModel.progressValue
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // ---------------- Status table + log --------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 14

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Theme.bgCard
                    border.color: Theme.border
                    border.width: 1
                    radius: 8

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: "DATABASE STATUS"
                                color: Theme.accent
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Text {
                                objectName: "lblRowSummary"
                                text: statusList.count + (statusList.count === 1 ? " row" : " rows")
                                color: Theme.muted
                                font.pixelSize: 11
                            }

                            Item { Layout.fillWidth: true }

                            // Client-side filter over already-scanned rows —
                            // never re-queries the database.
                            RowLayout {
                                spacing: 6
                                Image {
                                    source: "image://icons/search/muted"
                                    sourceSize.width: 13
                                    sourceSize.height: 13
                                    Layout.preferredWidth: 13
                                    Layout.preferredHeight: 13
                                }
                                TextField {
                                    objectName: "txtSearch"
                                    Layout.preferredWidth: 180
                                    placeholderText: "Search symbol / interval…"
                                    text: viewModel.searchText
                                    onTextEdited: viewModel.searchText = text
                                    color: Theme.textPrimary
                                    font.pixelSize: 11
                                    background: FieldBackground { implicitHeight: 26 }
                                }
                            }
                        }

                        // Column header
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 28
                            color: "#15171d"
                            radius: 4

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 6
                                Repeater {
                                    model: [
                                        { title: "SYMBOL", weight: 2 },
                                        { title: "INTERVAL", weight: 1 },
                                        { title: "FIRST RECORD", weight: 3 },
                                        { title: "LAST RECORD", weight: 3 },
                                        { title: "TOTAL", weight: 2 },
                                        { title: "STATUS", weight: 3 },
                                        { title: "ACTION", weight: 2 }
                                    ]
                                    Text {
                                        required property var modelData
                                        text: modelData.title
                                        color: Theme.muted
                                        font.pixelSize: 10
                                        font.bold: true
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: modelData.weight
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }

                        ListView {
                            id: statusList
                            objectName: "statusList"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: viewModel.statusModel
                            spacing: 1

                            ScrollBar.vertical: ScrollBar {}

                            Text {
                                anchors.centerIn: parent
                                visible: statusList.count === 0
                                text: viewModel.searchText === ""
                                      ? "No scan results yet — run a status scan."
                                      : "No rows match “" + viewModel.searchText + "”."
                                color: Theme.muted
                                font.pixelSize: 12
                            }

                            delegate: Rectangle {
                                id: statusRow
                                width: ListView.view.width
                                height: 34
                                color: index % 2 === 0 ? "transparent" : "#15171d"

                                required property int index
                                required property string symbol
                                required property string interval
                                required property string firstRecord
                                required property string lastRecord
                                required property string totalCandles
                                required property string statusText
                                required property bool isHealthy

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 6

                                    Text {
                                        text: statusRow.symbol
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 2
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: statusRow.interval
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                    }
                                    Text {
                                        text: statusRow.firstRecord
                                        color: Theme.muted
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 3
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: statusRow.lastRecord
                                        color: Theme.muted
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 3
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: statusRow.totalCandles
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 2
                                    }
                                    Text {
                                        text: statusRow.statusText
                                        color: statusRow.isHealthy ? Theme.success : Theme.danger
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 3
                                        elide: Text.ElideRight
                                    }

                                    Button {
                                        id: rowSyncButton
                                        objectName: "btnRowSync_" + statusRow.symbol
                                                    + "_" + statusRow.interval
                                        text: "Sync"
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 2
                                        enabled: viewModel.uiMode !== "LOCKED"
                                        onClicked: viewModel.requestSyncRow(
                                                       statusRow.symbol, statusRow.interval)

                                        contentItem: Text {
                                            text: rowSyncButton.text
                                            color: Theme.success
                                            font.pixelSize: 10
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                            opacity: rowSyncButton.enabled ? 1.0 : 0.4
                                        }
                                        background: Rectangle {
                                            implicitHeight: 22
                                            radius: 4
                                            color: rowSyncButton.hovered && rowSyncButton.enabled
                                                   ? "#1f2127" : "#17181d"
                                            border.color: Theme.success
                                            border.width: 1
                                            opacity: rowSyncButton.enabled ? 1.0 : 0.4
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                LogPanel {
                    objectName: "syncLogPanel"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 190
                    title: "SYNC LOG"
                    logModel: viewModel.logModel
                }
            }
        }
    }
}
