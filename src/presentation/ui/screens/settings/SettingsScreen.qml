import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// API & Credentials screen (BOT-030 Phase 2). Same 5 fields and the same
// in-memory-only save semantics as the QtWidgets version it replaces —
// IConfig still has no disk-write path, which the warning banner states
// plainly rather than implying a persistence that doesn't exist.
Rectangle {
    id: root

    color: Theme.bg

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: root.width
            spacing: 0

            // ---- Card ------------------------------------------------
            Rectangle {
                Layout.fillWidth: true
                Layout.margins: 20
                // Header + body + the body's top/bottom anchor margins. Without
                // counting those margins the card clips its last row (the
                // status line) right at the bottom edge.
                Layout.preferredHeight: cardHeader.height
                                        + cardBody.implicitHeight
                                        + cardBody.anchors.margins * 2
                color: Theme.bgCard
                border.color: Theme.border
                border.width: 1
                radius: 8

                // ---- Card header ------------------------------------
                Rectangle {
                    id: cardHeader
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 56
                    color: Theme.bgCardHeader
                    radius: 8

                    // Squares off the bottom corners so only the top ones
                    // stay rounded where the header meets the card body.
                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: parent.radius
                        color: parent.color
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        height: 1
                        color: Theme.border
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 15
                        anchors.rightMargin: 15
                        spacing: 10

                        Image {
                            source: "image://icons/settings/accent"
                            sourceSize.width: 20
                            sourceSize.height: 20
                            Layout.preferredWidth: 20
                            Layout.preferredHeight: 20
                        }

                        ColumnLayout {
                            spacing: 0
                            Text {
                                text: "SAGITTARIUS API KEYS VAULT"
                                color: Theme.accent
                                font.pixelSize: 14
                                font.bold: true
                            }
                            Text {
                                text: "HMAC SHA256 API Key & Secret Management"
                                color: Theme.muted
                                font.pixelSize: 11
                            }
                        }

                        Item { Layout.fillWidth: true }

                        Button {
                            id: saveButton
                            objectName: "btnSaveCredentials"
                            text: "Save Credentials"
                            onClicked: viewModel.requestSave()

                            contentItem: Text {
                                text: saveButton.text
                                color: Theme.bg
                                font.pixelSize: 12
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }

                            background: Rectangle {
                                radius: 6
                                implicitWidth: 150
                                implicitHeight: 32
                                color: saveButton.down
                                       ? Qt.darker(Theme.accent, 1.2)
                                       : Theme.accent
                            }
                        }
                    }
                }

                // ---- Card body --------------------------------------
                ColumnLayout {
                    id: cardBody
                    anchors.top: cardHeader.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: 15
                    spacing: 14

                    Text {
                        objectName: "lblRestartWarning"
                        Layout.fillWidth: true
                        text: "Thay đổi chỉ áp dụng trong bộ nhớ của phiên chạy hiện tại "
                              + "— chưa ghi xuống user_config.json. API Key/Secret cần "
                              + "khởi động lại app để có hiệu lực."
                        color: Theme.accent
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 14
                        rowSpacing: 12

                        // --- API Key ---
                        Text {
                            text: "Binance API Key (Public):"
                            color: Theme.textPrimary
                            font.pixelSize: 12
                        }
                        TextField {
                            objectName: "txtApiKey"
                            Layout.fillWidth: true
                            text: viewModel.apiKey
                            onTextEdited: viewModel.apiKey = text
                            color: Theme.accent
                            font.family: "Consolas"
                            background: Rectangle {
                                color: "#17181d"
                                border.color: Theme.border
                                border.width: 1
                                radius: 6
                                implicitHeight: 34
                            }
                        }

                        // --- API Secret (masked, with reveal toggle) ---
                        Text {
                            text: "Binance API Secret (Private):"
                            color: Theme.textPrimary
                            font.pixelSize: 12
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            TextField {
                                id: secretField
                                objectName: "txtApiSecret"
                                Layout.fillWidth: true
                                text: viewModel.apiSecret
                                onTextEdited: viewModel.apiSecret = text
                                echoMode: revealSecret.checked
                                          ? TextInput.Normal : TextInput.Password
                                color: Theme.textPrimary
                                font.family: "Consolas"
                                background: Rectangle {
                                    color: "#17181d"
                                    border.color: Theme.border
                                    border.width: 1
                                    radius: 6
                                    implicitHeight: 34
                                }
                            }

                            Button {
                                id: revealSecret
                                objectName: "btnRevealSecret"
                                checkable: true
                                implicitWidth: 36
                                implicitHeight: 34
                                ToolTip.visible: hovered
                                ToolTip.text: checked ? "Hide secret" : "Show secret"

                                contentItem: Image {
                                    source: revealSecret.checked
                                            ? "image://icons/eye-off/muted"
                                            : "image://icons/eye/muted"
                                    sourceSize.width: 16
                                    sourceSize.height: 16
                                    fillMode: Image.Pad
                                    horizontalAlignment: Image.AlignHCenter
                                    verticalAlignment: Image.AlignVCenter
                                }

                                background: Rectangle {
                                    color: revealSecret.hovered ? "#1f2127" : "#17181d"
                                    border.color: Theme.border
                                    border.width: 1
                                    radius: 6
                                }
                            }
                        }

                        // --- Default symbols ---
                        Text {
                            text: "Default Symbols:"
                            color: Theme.textPrimary
                            font.pixelSize: 12
                        }
                        TextField {
                            objectName: "txtDefaultSymbols"
                            Layout.fillWidth: true
                            text: viewModel.defaultSymbols
                            onTextEdited: viewModel.defaultSymbols = text
                            placeholderText: "BTCUSDT, ETHUSDT"
                            color: Theme.textPrimary
                            background: Rectangle {
                                color: "#17181d"
                                border.color: Theme.border
                                border.width: 1
                                radius: 6
                                implicitHeight: 34
                            }
                        }

                        // --- Default interval ---
                        Text {
                            text: "Default Interval:"
                            color: Theme.textPrimary
                            font.pixelSize: 12
                        }
                        TextField {
                            objectName: "txtDefaultInterval"
                            Layout.fillWidth: true
                            text: viewModel.defaultInterval
                            onTextEdited: viewModel.defaultInterval = text
                            placeholderText: "1m"
                            color: Theme.textPrimary
                            background: Rectangle {
                                color: "#17181d"
                                border.color: Theme.border
                                border.width: 1
                                radius: 6
                                implicitHeight: 34
                            }
                        }

                        // --- Default sync days ---
                        Text {
                            text: "Default Sync Days:"
                            color: Theme.textPrimary
                            font.pixelSize: 12
                        }
                        SpinBox {
                            id: syncDaysSpin
                            objectName: "spinDefaultSyncDays"
                            from: 1
                            to: 3650
                            editable: true
                            value: viewModel.defaultSyncDays
                            onValueModified: viewModel.defaultSyncDays = value

                            // The Basic style's default SpinBox is light-themed
                            // and would sit as a white block in this dark card,
                            // so every part is restyled explicitly.
                            contentItem: TextInput {
                                text: syncDaysSpin.textFromValue(
                                          syncDaysSpin.value, syncDaysSpin.locale)
                                color: Theme.textPrimary
                                horizontalAlignment: Qt.AlignHCenter
                                verticalAlignment: Qt.AlignVCenter
                                readOnly: !syncDaysSpin.editable
                                validator: syncDaysSpin.validator
                                selectByMouse: true
                                selectionColor: Theme.accent
                            }

                            background: Rectangle {
                                implicitWidth: 130
                                implicitHeight: 34
                                color: "#17181d"
                                border.color: Theme.border
                                border.width: 1
                                radius: 6
                            }

                            up.indicator: Rectangle {
                                x: syncDaysSpin.mirrored ? 0 : parent.width - width
                                height: parent.height
                                implicitWidth: 30
                                color: syncDaysSpin.up.pressed ? "#2a2d36" : "transparent"
                                Text {
                                    anchors.centerIn: parent
                                    text: "+"
                                    color: Theme.muted
                                    font.pixelSize: 14
                                }
                            }

                            down.indicator: Rectangle {
                                x: syncDaysSpin.mirrored ? parent.width - width : 0
                                height: parent.height
                                implicitWidth: 30
                                color: syncDaysSpin.down.pressed ? "#2a2d36" : "transparent"
                                Text {
                                    anchors.centerIn: parent
                                    text: "−"
                                    color: Theme.muted
                                    font.pixelSize: 14
                                }
                            }
                        }
                    }

                    Text {
                        objectName: "lblStatus"
                        Layout.fillWidth: true
                        // Deliberately always laid out (no `visible:` toggle and
                        // no conditional Layout.preferredHeight). Both were tried
                        // and both left this label stranded at y=0, drawn on top
                        // of the warning banner: a ColumnLayout skips invisible
                        // children and doesn't re-run when that flips, and a
                        // preferredHeight that reads its own implicitHeight is a
                        // binding cycle the layout abandons. The cost is one
                        // empty line of padding while there's no message — a fair
                        // trade for a layout that is always correct.
                        text: viewModel.statusMessage
                        color: viewModel.statusIsError ? Theme.danger : Theme.success
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
