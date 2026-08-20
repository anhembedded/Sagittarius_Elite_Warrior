import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

// Database screen (Storage Vault — BOT-112A).
Rectangle {
    id: root

    color: Theme.bg

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

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

        // ================= Header + Real Functional Actions ================
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
                    text: "Historical Market KLines Multi-Timeframe Database Hub"
                    color: Theme.muted
                    font.pixelSize: 11
                }
            }

            Item { Layout.fillWidth: true }

            // Functional Header Action: Vacuum / Optimize DB
            Button {
                id: btnVacuum
                objectName: "btnVacuum"
                text: "Tối ưu hóa Database (Vacuum)"
                enabled: root.hasViewModel && viewModel.uiMode === "IDLE"
                onClicked: if (root.hasViewModel) viewModel.requestVacuum()

                contentItem: RowLayout {
                    spacing: 6
                    Image {
                        source: "image://icons/zap/accent"
                        sourceSize.width: 14
                        sourceSize.height: 14
                        Layout.preferredWidth: 14
                        Layout.preferredHeight: 14
                    }
                    Text {
                        text: btnVacuum.text
                        color: Theme.accent
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
                background: Rectangle {
                    implicitHeight: 30
                    radius: 6
                    color: btnVacuum.hovered && btnVacuum.enabled ? "#1f2127" : "#131418"
                    border.color: Theme.accent
                    border.width: 1
                }
            }

            // Functional Header Action: Purge All Vault
            Button {
                id: btnPurgeVault
                objectName: "btnPurgeVault"
                text: "Xóa toàn bộ Vault (Purge)"
                enabled: root.hasViewModel && viewModel.uiMode === "IDLE"
                onClicked: purgeConfirmDialog.open()

                contentItem: RowLayout {
                    spacing: 6
                    Image {
                        source: "image://icons/trash-2/danger"
                        sourceSize.width: 14
                        sourceSize.height: 14
                        Layout.preferredWidth: 14
                        Layout.preferredHeight: 14
                    }
                    Text {
                        text: btnPurgeVault.text
                        color: Theme.danger
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
                background: Rectangle {
                    implicitHeight: 30
                    radius: 6
                    color: btnPurgeVault.hovered && btnPurgeVault.enabled ? "#2a1518" : "#131418"
                    border.color: Theme.danger
                    border.width: 1
                }
            }
        }

        // ========================= Stat tiles =========================
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Repeater {
                model: [
                    { label: "Stored KLines Records", value: root.hasViewModel ? viewModel.storedRecords : "—",
                      hint: "across scanned symbol/interval pairs" },
                    { label: "Est. Database Size", value: root.hasViewModel ? viewModel.databaseSize : "—",
                      hint: "on-disk SQLite storage files (WAL mode)" }
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
                Layout.preferredWidth: 320
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

                    SectionLabel { text: "TARGET & TIMEFRAME" }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 8
                        rowSpacing: 8

                        Text { text: "Symbol:"; color: Theme.textPrimary; font.pixelSize: 12 }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            ComboBox {
                                id: cboSymbol
                                objectName: "cboSymbol"
                                Layout.fillWidth: true
                                model: root.hasViewModel ? viewModel.symbols : []
                                editable: true
                                enabled: root.hasViewModel && viewModel.uiMode === "IDLE"
                                currentIndex: root.hasViewModel ? Math.max(0, viewModel.symbols.indexOf(viewModel.selectedSymbol)) : 0
                                onCurrentTextChanged: if (root.hasViewModel && currentText.trim()) viewModel.selectedSymbol = currentText
                                onEditTextChanged: if (root.hasViewModel && editText.trim()) viewModel.selectedSymbol = editText
                                background: FieldBackground {}
                                contentItem: Text {
                                    leftPadding: 8
                                    text: cboSymbol.editText
                                    color: Theme.textPrimary
                                    font.pixelSize: 12
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Button {
                                id: btnSearchSymbol
                                objectName: "btnSearchSymbol"
                                implicitWidth: 32
                                implicitHeight: 32
                                enabled: root.hasViewModel && viewModel.uiMode === "IDLE"
                                ToolTip.visible: hovered
                                ToolTip.text: "Tìm kiếm nhanh trong 1.361+ mã Binance"
                                onClicked: symbolPickerModal.open()

                                contentItem: Image {
                                    source: "image://icons/search/" + (btnSearchSymbol.hovered ? "accent" : "muted")
                                    sourceSize.width: 14
                                    sourceSize.height: 14
                                    anchors.centerIn: parent
                                }
                                background: Rectangle {
                                    radius: 6
                                    color: btnSearchSymbol.hovered ? "#1f2127" : "#17181d"
                                    border.color: btnSearchSymbol.hovered ? Theme.accent : Theme.border
                                    border.width: 1
                                }
                            }
                        }

                        Text { text: "Timeframe:"; color: Theme.textPrimary; font.pixelSize: 12 }
                        ComboBox {
                            id: cboInterval
                            objectName: "cboInterval"
                            Layout.fillWidth: true
                            model: root.hasViewModel ? viewModel.intervals : []
                            enabled: root.hasViewModel && viewModel.uiMode === "IDLE"
                            currentIndex: root.hasViewModel ? Math.max(0, viewModel.intervals.indexOf(viewModel.selectedInterval)) : 0
                            onCurrentTextChanged: if (root.hasViewModel && currentText.trim()) viewModel.selectedInterval = currentText
                            background: FieldBackground {}
                            contentItem: Text {
                                leftPadding: 8
                                text: cboInterval.currentText
                                color: Theme.textPrimary
                                font.pixelSize: 12
                                font.bold: true
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    TimeRangeCard {
                        Layout.fillWidth: true
                        color: "transparent"
                        border.width: 0
                        useCustomTime: root.hasViewModel ? viewModel.useCustomTime : false
                        readOnly: !root.hasViewModel || viewModel.uiMode !== "IDLE"
                        fromDateTime: root.hasViewModel ? viewModel.fromDateTime : ""
                        toDateTime: root.hasViewModel ? viewModel.toDateTime : ""

                        onCustomTimeToggled: checked => { if (root.hasViewModel) viewModel.useCustomTime = checked; }
                        onFromDateTimeEdited: text => { if (root.hasViewModel) viewModel.fromDateTime = text; }
                        onToDateTimeEdited: text => { if (root.hasViewModel) viewModel.toDateTime = text; }
                    }

                    SectionLabel { text: "ACTIONS" }

                    Repeater {
                        model: [
                            { name: "btnCheckStatus", label: "Scan Current Status",
                              icon: "database", tint: "muted", action: "checkStatus" },
                            { name: "btnCheckAll", label: "Scan All Shards & Timeframes",
                              icon: "layout-dashboard", tint: "muted", action: "checkAll" },
                            { name: "btnSyncData", label: "Sync Current Timeframe",
                              icon: "play", tint: "success", action: "sync" },
                            { name: "btnSyncAllGaps", label: "Sync All Gaps",
                              icon: "clock", tint: "success", action: "syncAllGaps" },
                            { name: "btnClearData", label: "Clear Selected Local Data",
                              icon: "trash-2", tint: "danger", action: "clearData" }
                        ]

                        Button {
                            id: actionButton
                            required property var modelData
                            objectName: modelData.name
                            text: modelData.label
                            Layout.fillWidth: true
                            enabled: root.hasViewModel && viewModel.uiMode === "IDLE"

                            onClicked: {
                                if (!root.hasViewModel) return;
                                switch (modelData.action) {
                                case "checkStatus": viewModel.requestCheckStatus(); break;
                                case "checkAll": viewModel.requestCheckAllStatus(); break;
                                case "sync": viewModel.requestSync(); break;
                                case "syncAllGaps": viewModel.requestSyncAllGaps(); break;
                                case "clearData": clearConfirmDialog.open(); break;
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
                        id: syncProgress
                        objectName: "syncProgress"
                        Layout.fillWidth: true
                        visible: root.hasViewModel && viewModel.progressVisible
                        indeterminate: !root.hasViewModel || viewModel.progressMaximum === 0
                        from: 0
                        to: root.hasViewModel ? Math.max(1, viewModel.progressMaximum) : 1
                        value: root.hasViewModel ? viewModel.progressValue : 0

                        background: Rectangle {
                            implicitHeight: 8
                            color: "#1e1e24"
                            radius: 4
                            border.color: "#33ffffff"
                            border.width: 1
                        }

                        contentItem: Item {
                            implicitHeight: 8

                            Rectangle {
                                visible: !syncProgress.indeterminate
                                width: syncProgress.visualPosition * parent.width
                                height: parent.height
                                radius: 4
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0.0; color: Theme.accent }
                                    GradientStop { position: 1.0; color: "#00f0ff" }
                                }
                                Behavior on width {
                                    NumberAnimation { duration: 300; easing.type: Easing.OutQuart }
                                }
                            }

                            Rectangle {
                                id: indetRect
                                visible: syncProgress.indeterminate
                                width: parent.width * 0.4
                                height: parent.height
                                radius: 4
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0.0; color: "transparent" }
                                    GradientStop { position: 0.5; color: Theme.accent }
                                    GradientStop { position: 1.0; color: "transparent" }
                                }
                                SequentialAnimation on x {
                                    loops: Animation.Infinite
                                    running: syncProgress.indeterminate && syncProgress.visible
                                    NumberAnimation {
                                        from: -indetRect.width
                                        to: syncProgress.width
                                        duration: 1200
                                        easing.type: Easing.InOutQuad
                                    }
                                }
                            }
                        }
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
                                text: statusList.count + (statusList.count === 1 ? " table" : " tables")
                                color: Theme.muted
                                font.pixelSize: 11
                            }

                            Item { Layout.fillWidth: true }

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
                                    placeholderText: "Search symbol / timeframe…"
                                    text: root.hasViewModel ? viewModel.searchText : ""
                                    onTextEdited: if (root.hasViewModel) viewModel.searchText = text
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
                                        { title: "SYMBOL", weight: 2.2 },
                                        { title: "TF", weight: 1.0 },
                                        { title: "FIRST RECORD", weight: 2.8 },
                                        { title: "LAST RECORD", weight: 2.8 },
                                        { title: "TOTAL", weight: 1.8 },
                                        { title: "STATUS", weight: 2.2 },
                                        { title: "ACTIONS", weight: 2.6 }
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
                            model: root.hasViewModel ? viewModel.statusModel : null
                            spacing: 1

                            ScrollBar.vertical: ScrollBar {}

                            Text {
                                anchors.centerIn: parent
                                visible: statusList.count === 0
                                text: !root.hasViewModel || viewModel.searchText === ""
                                      ? "Đang quét Storage Vault..."
                                      : "Không tìm thấy dữ liệu khớp với “" + (root.hasViewModel ? viewModel.searchText : "") + "”."
                                color: Theme.muted
                                font.pixelSize: 12
                            }

                            delegate: Rectangle {
                                id: statusRow
                                width: ListView.view.width
                                height: 36
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
                                        font.bold: true
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 2.2
                                        elide: Text.ElideRight
                                    }

                                    Rectangle {
                                        Layout.preferredWidth: 1.0
                                        Layout.fillWidth: true
                                        implicitHeight: 20
                                        color: "#1a1d29"
                                        radius: 4
                                        border.color: Theme.accent
                                        border.width: 1

                                        Text {
                                            anchors.centerIn: parent
                                            text: statusRow.interval || "1m"
                                            color: Theme.accent
                                            font.pixelSize: 10
                                            font.bold: true
                                        }
                                    }

                                    Text {
                                        text: statusRow.firstRecord
                                        color: Theme.muted
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 2.8
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: statusRow.lastRecord
                                        color: Theme.muted
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 2.8
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: statusRow.totalCandles
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1.8
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 2.2
                                        implicitHeight: 22
                                        color: statusRow.isHealthy ? "transparent" : "#2a1518"
                                        radius: 4
                                        border.color: statusRow.isHealthy ? "transparent" : Theme.danger
                                        border.width: statusRow.isHealthy ? 0 : 1

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 4
                                            anchors.rightMargin: 4
                                            spacing: 4

                                            Text {
                                                text: statusRow.statusText
                                                color: statusRow.isHealthy ? Theme.success : Theme.danger
                                                font.pixelSize: 11
                                                font.bold: true
                                                Layout.fillWidth: true
                                                elide: Text.ElideRight
                                                verticalAlignment: Text.AlignVCenter
                                            }

                                            Image {
                                                visible: !statusRow.isHealthy
                                                source: "image://icons/alert-triangle/danger"
                                                sourceSize.width: 12
                                                sourceSize.height: 12
                                                Layout.preferredWidth: 12
                                                Layout.preferredHeight: 12
                                            }
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: !statusRow.isHealthy ? Qt.PointingHandCursor : Qt.ArrowCursor
                                            enabled: !statusRow.isHealthy
                                            onClicked: {
                                                if (root.hasViewModel) {
                                                    viewModel.requestInspectGaps(statusRow.symbol, statusRow.interval || "1m");
                                                }
                                            }
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 2.6
                                                        Button {
                                            id: rowInspectKlinesButton
                                            objectName: "btnRowInspectKlines_" + statusRow.symbol + "_" + (statusRow.interval || "1m")
                                            text: "KLines"
                                            Layout.fillWidth: true
                                            enabled: root.hasViewModel && viewModel.uiMode === "IDLE"
                                            onClicked: if (root.hasViewModel) viewModel.requestInspectKlines(statusRow.symbol, statusRow.interval || "1m")

                                            contentItem: Text {
                                                text: rowInspectKlinesButton.text
                                                color: Theme.accent
                                                font.pixelSize: 10
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                                opacity: rowInspectKlinesButton.enabled ? 1.0 : 0.4
                                            }
                                            background: Rectangle {
                                                implicitHeight: 22
                                                radius: 4
                                                color: rowInspectKlinesButton.hovered && rowInspectKlinesButton.enabled
                                                       ? "#1f2a3a" : "#131822"
                                                border.color: Theme.accent
                                                border.width: 1
                                                opacity: rowInspectKlinesButton.enabled ? 1.0 : 0.4
                                            }
                                        }

                                        Button {
                                            id: rowInspectButton
                                            objectName: "btnRowInspect_" + statusRow.symbol + "_" + (statusRow.interval || "1m")
                                            text: "Gaps"
                                            visible: !statusRow.isHealthy
                                            Layout.fillWidth: true
                                            enabled: root.hasViewModel && viewModel.uiMode === "IDLE"
                                            onClicked: if (root.hasViewModel) viewModel.requestInspectGaps(statusRow.symbol, statusRow.interval || "1m")

                                            contentItem: Text {
                                                text: rowInspectButton.text
                                                color: Theme.accent
                                                font.pixelSize: 10
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                                opacity: rowInspectButton.enabled ? 1.0 : 0.4
                                            }
                                            background: Rectangle {
                                                implicitHeight: 22
                                                radius: 4
                                                color: rowInspectButton.hovered && rowInspectButton.enabled
                                                       ? "#1f2a3a" : "#131822"
                                                border.color: Theme.accent
                                                border.width: 1
                                                opacity: rowInspectButton.enabled ? 1.0 : 0.4
                                            }
                                        }

                                        Button {
                                            id: rowSyncButton
                                            objectName: "btnRowSync_" + statusRow.symbol + "_" + (statusRow.interval || "1m")
                                            text: "Sync"
                                            Layout.fillWidth: true
                                            enabled: root.hasViewModel && viewModel.uiMode === "IDLE"
                                            onClicked: if (root.hasViewModel) viewModel.requestSyncRow(statusRow.symbol, statusRow.interval || "1m")

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

                                        Button {
                                            id: rowClearButton
                                            objectName: "btnRowClear_" + statusRow.symbol + "_" + (statusRow.interval || "1m")
                                            text: "Clear"
                                            Layout.fillWidth: true
                                            enabled: root.hasViewModel && viewModel.uiMode === "IDLE"
                                            onClicked: if (root.hasViewModel) viewModel.requestClearRow(statusRow.symbol, statusRow.interval || "1m")

                                            contentItem: Text {
                                                text: rowClearButton.text
                                                color: Theme.danger
                                                font.pixelSize: 10
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                                opacity: rowClearButton.enabled ? 1.0 : 0.4
                                            }
                                            background: Rectangle {
                                                implicitHeight: 22
                                                radius: 4
                                                color: rowClearButton.hovered && rowClearButton.enabled
                                                       ? "#2b1414" : "#191212"
                                                border.color: Theme.danger
                                                border.width: 1
                                                opacity: rowClearButton.enabled ? 1.0 : 0.4
                                            }
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
                    logModel: root.hasViewModel ? viewModel.logModel : null
                }
            }
        }
    }

    // ==================================================================
    // Modals & Confirmation Dialogs
    // ==================================================================

    SymbolPickerModal {
        id: symbolPickerModal
        objectName: "symbolPickerModal"
    }

    GapInspectorModal {
        id: gapInspectorModal
        objectName: "gapInspectorModal"
    }

    KLineInspectorModal {
        id: klineInspectorModal
        objectName: "klineInspectorModal"
    }

    Connections {
        target: root.hasViewModel ? viewModel : null
        function onOpenGapInspectorRequested() {
            gapInspectorModal.open()
        }
        function onOpenKlineInspectorRequested() {
            klineInspectorModal.open()
        }
    }

    ModalDialogCard {
        id: clearConfirmDialog
        objectName: "clearConfirmDialog"
        title: "XÁC NHẬN XÓA DỮ LIỆU"
        subtitle: "Xóa các nến đã lưu trong SQLite shard"
        iconSource: "image://icons/trash-2/danger"
        preferredWidth: 420
        preferredHeight: 220

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            Text {
                Layout.fillWidth: true
                text: "Bạn có chắc chắn muốn xóa toàn bộ nến của " + (root.hasViewModel ? (viewModel.selectedSymbol + " (" + viewModel.selectedInterval + ")") : "") + " không?"
                color: Theme.textPrimary
                font.pixelSize: 13
                wrapMode: Text.Wrap
            }

            Text {
                Layout.fillWidth: true
                text: "Thao tác này sẽ giải phóng dung lượng đĩa và làm trống bảng klines tương ứng."
                color: Theme.muted
                font.pixelSize: 11
                wrapMode: Text.Wrap
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Button {
                    Layout.fillWidth: true
                    text: "Hủy bỏ"
                    onClicked: clearConfirmDialog.close()
                    background: Rectangle {
                        implicitHeight: 34
                        radius: 6
                        color: "#1c202d"
                        border.color: Theme.border
                        border.width: 1
                    }
                    contentItem: Text {
                        text: "Hủy bỏ"
                        color: Theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 12
                    }
                }

                Button {
                    id: btnConfirmClear
                    objectName: "btnConfirmClear"
                    Layout.fillWidth: true
                    text: "Xác nhận Xóa"
                    onClicked: {
                        clearConfirmDialog.close()
                        viewModel.requestClearData()
                    }
                    background: Rectangle {
                        implicitHeight: 34
                        radius: 6
                        color: btnConfirmClear.hovered ? "#e02e2e" : Theme.danger
                    }
                    contentItem: Text {
                        text: btnConfirmClear.text
                        color: "#ffffff"
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 12
                    }
                }
            }
        }
    }

    ModalDialogCard {
        id: purgeConfirmDialog
        objectName: "purgeConfirmDialog"
        title: "CẢNH BÁO NGUY HIỂM — PURGE VAULT"
        subtitle: "Xóa toàn bộ database SQLite"
        iconSource: "image://icons/alert-triangle/danger"
        preferredWidth: 460
        preferredHeight: 240

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            Text {
                Layout.fillWidth: true
                text: "CẢNH BÁO NGUY HIỂM: Bạn đang chuẩn bị xóa TOÀN BỘ dữ liệu của tất cả các symbol trong Storage Vault!"
                color: Theme.danger
                font.pixelSize: 13
                font.bold: true
                wrapMode: Text.Wrap
            }

            Text {
                Layout.fillWidth: true
                text: "Hành động này sẽ xóa tất cả các file SQLite shard (.db) và không thể hoàn tác."
                color: Theme.muted
                font.pixelSize: 11
                wrapMode: Text.Wrap
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Button {
                    Layout.fillWidth: true
                    text: "Hủy bỏ"
                    onClicked: purgeConfirmDialog.close()
                    background: Rectangle {
                        implicitHeight: 34
                        radius: 6
                        color: "#1c202d"
                        border.color: Theme.border
                        border.width: 1
                    }
                    contentItem: Text {
                        text: "Hủy bỏ"
                        color: Theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 12
                    }
                }

                Button {
                    id: btnConfirmPurge
                    objectName: "btnConfirmPurge"
                    Layout.fillWidth: true
                    text: "XÓA TOÀN BỘ (PURGE)"
                    onClicked: {
                        purgeConfirmDialog.close()
                        viewModel.requestPurgeAll()
                    }
                    background: Rectangle {
                        implicitHeight: 34
                        radius: 6
                        color: btnConfirmPurge.hovered ? "#c01010" : Theme.danger
                    }
                    contentItem: Text {
                        text: btnConfirmPurge.text
                        color: "#ffffff"
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 12
                    }
                }
            }
        }
    }
}
