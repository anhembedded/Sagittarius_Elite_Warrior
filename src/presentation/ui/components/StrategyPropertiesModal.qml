import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "."

// StrategyPropertiesModal (BOT-104) — 4-tab TradingView-style Strategy Properties Dialog:
// 1. "Các đầu vào" (Inputs) — Strategy-declared dynamic parameters.
// 2. "Đặc tính" (Properties) — Capital, Order Size, Pyramiding, Commission, Slippage, Leverage.
// 3. "Định dạng" (Style) — Visual styling & plot toggles.
// 4. "Hiển thị" (Visibility) — Timeframe visibility filters.
ModalDialogCard {
    id: root
    property string strategyName: ""
    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null
    readonly property int parameterGroupCount: root.hasViewModel ? viewModel.botParamsSchema.length : 0
    readonly property int parameterRowCount: root.hasViewModel ? viewModel.botParamsRows.length : 0

    title: "CÀI ĐẶT CHIẾN LƯỢC: " + (root.strategyName ? root.strategyName.toUpperCase() : "THÔNG SỐ")
    iconSource: "image://icons/sliders/accent"
    preferredWidth: 680
    preferredHeight: 620

    Connections {
        target: typeof viewModel === "undefined" ? null : viewModel
        function onBotParamsSaved() { root.close() }
    }

    Shortcut {
        sequence: "Ctrl+Return"
        context: Qt.WindowShortcut
        enabled: root.visible && root.hasViewModel
        onActivated: root.saveAndRerun()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // --- 4-Tab Navigation Header ---
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Repeater {
                model: [
                    { id: "inputs", label: "Các đầu vào", icon: "sliders" },
                    { id: "properties", label: "Đặc tính", icon: "settings" },
                    { id: "style", label: "Định dạng", icon: "eye" },
                    { id: "visibility", label: "Hiển thị", icon: "clock" }
                ]

                Rectangle {
                    required property var modelData
                    required property int index
                    readonly property bool isSelected: tabStack.currentIndex === index
                    Layout.fillWidth: true
                    height: 36
                    radius: 6
                    color: isSelected ? (Theme && Theme.surface ? Theme.surface : "#1e222d") : "transparent"
                    border.color: isSelected ? (Theme && Theme.border ? Theme.border : "#2a2e39") : "transparent"
                    border.width: 1

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 6

                        Image {
                            source: "image://icons/" + modelData.icon + "/" + (isSelected ? "accent" : "muted")
                            sourceSize: Qt.size(14, 14)
                        }

                        Text {
                            text: modelData.label
                            textFormat: Text.PlainText
                            color: isSelected ? (Theme && Theme.accent ? Theme.accent : "#f0b90b") : (Theme && Theme.muted ? Theme.muted : "#9aa4b2")
                            font.pixelSize: 12
                            font.bold: isSelected
                        }
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: parent.width - 16
                        height: 2
                        radius: 1
                        color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                        visible: isSelected
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: tabStack.currentIndex = index
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme && Theme.border ? Theme.border : "#2a2d3e"
        }

        // --- Tab Stack Container ---
        StackLayout {
            id: tabStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: 0

            // ==========================================
            // TAB 1: Các đầu vào (Strategy Inputs)
            // ==========================================
            ScrollView {
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    id: inputsColumn
                    objectName: "strategyInputsContent"
                    width: tabStack.width - 24
                    spacing: 14

                    Text {
                        Layout.fillWidth: true
                        visible: root.parameterGroupCount === 0
                        text: "Chiến lược này không có tham số đầu vào nào để cấu hình."
                        color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                        font.pixelSize: 11
                    }

                    Repeater {
                        model: root.hasViewModel ? viewModel.botParamsRows : []

                        ColumnLayout {
                            required property var modelData
                            readonly property string rowType: modelData.rowType
                            readonly property string groupLabel: modelData.groupLabel
                            readonly property var field: modelData.field
                            objectName: "botParamRow_" + rowType + "_" + (field.name || "")
                            Layout.fillWidth: true
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                visible: rowType === "header"

                                Image {
                                    source: "image://icons/sliders/accent"
                                    sourceSize: Qt.size(13, 13)
                                }

                                Text {
                                    text: rowType === "header" ? groupLabel.toUpperCase() : ""
                                    textFormat: Text.PlainText
                                    color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.letterSpacing: 0.5
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 1
                                    color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                                }
                            }

                            BotParamField {
                                Layout.fillWidth: true
                                visible: rowType === "field"
                                fieldData: rowType === "field" ? field : null
                            }
                        }
                    }
                }
            }

            // ==========================================
            // TAB 2: Đặc tính (Broker Properties & Sizing)
            // ==========================================
            ScrollView {
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    id: propertiesColumn
                    objectName: "strategyPropertiesContent"
                    width: tabStack.width - 24
                    spacing: 16

                    // Group 1: Vốn & Tiền tệ
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            Image {
                                source: "image://icons/dollar-sign/accent"
                                sourceSize: Qt.size(13, 13)
                            }
                            Text {
                                text: "VỐN BAN ĐẦU & TIỀN TỆ"
                                textFormat: Text.PlainText
                                color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme && Theme.border ? Theme.border : "#2a2d3e" }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Text {
                                    text: "Vốn ban đầu"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                TextField {
                                    id: propInitialCapital
                                    objectName: "propInitialCapital"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    text: root.hasViewModel ? viewModel.initialCapitalText : "10000"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    background: Rectangle {
                                        color: "#181a26"
                                        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                                        radius: 4
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.preferredWidth: 140
                                spacing: 4
                                Text {
                                    text: "Đơn vị tiền tệ"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                ComboBox {
                                    id: propCurrency
                                    objectName: "propCurrency"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    model: ["USD", "USDT", "BTC", "VND"]
                                    currentIndex: root.hasViewModel ? Math.max(0, model.indexOf(viewModel.selectedCurrency)) : 0
                                    background: Rectangle {
                                        color: "#181a26"
                                        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                                        radius: 4
                                    }
                                }
                            }
                        }
                    }

                    // Group 2: Khối lượng & Nhồi lệnh
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            Image {
                                source: "image://icons/sliders/accent"
                                sourceSize: Qt.size(13, 13)
                            }
                            Text {
                                text: "KÍCH THƯỚC LỆNH & KIM TỰ THÁP (PYRAMIDING)"
                                textFormat: Text.PlainText
                                color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme && Theme.border ? Theme.border : "#2a2d3e" }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            ColumnLayout {
                                Layout.preferredWidth: 180
                                spacing: 4
                                Text {
                                    text: "Loại kích thước lệnh"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                ComboBox {
                                    id: propOrderSizeType
                                    objectName: "propOrderSizeType"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    model: [
                                        { text: "% Vốn cổ phần (Equity)", value: "percent_of_equity" },
                                        { text: "USD Cố định (Cash)", value: "fixed_cash" },
                                        { text: "Hợp đồng / Coin", value: "fixed_contracts" }
                                    ]
                                    textRole: "text"
                                    valueRole: "value"
                                    currentIndex: root.hasViewModel ? (viewModel.orderSizeType === "fixed_cash" ? 1 : (viewModel.orderSizeType === "fixed_contracts" ? 2 : 0)) : 0
                                    background: Rectangle {
                                        color: "#181a26"
                                        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                                        radius: 4
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Text {
                                    text: "Giá trị kích thước"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                TextField {
                                    id: propOrderSizeValue
                                    objectName: "propOrderSizeValue"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    text: root.hasViewModel ? viewModel.orderSizeText : "100"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    background: Rectangle {
                                        color: "#181a26"
                                        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                                        radius: 4
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.preferredWidth: 140
                                spacing: 4
                                Text {
                                    text: "Kim tự tháp (Lệnh tối đa)"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                SpinBox {
                                    id: propPyramiding
                                    objectName: "propPyramiding"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    from: 1
                                    to: 10
                                    value: root.hasViewModel ? viewModel.pyramiding : 1
                                }
                            }
                        }
                    }

                    // Group 3: Phí hoa hồng & Trượt giá
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            Image {
                                source: "image://icons/settings/accent"
                                sourceSize: Qt.size(13, 13)
                            }
                            Text {
                                text: "HOA HỒNG & TRƯỢT GIÁ (SLIPPAGE)"
                                textFormat: Text.PlainText
                                color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme && Theme.border ? Theme.border : "#2a2d3e" }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            ColumnLayout {
                                Layout.preferredWidth: 180
                                spacing: 4
                                Text {
                                    text: "Loại hoa hồng"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                ComboBox {
                                    id: propCommissionType
                                    objectName: "propCommissionType"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    model: [
                                        { text: "% Giá trị lệnh", value: "percent" },
                                        { text: "USD / Lệnh", value: "cash_per_order" },
                                        { text: "USD / Hợp đồng", value: "cash_per_contract" }
                                    ]
                                    textRole: "text"
                                    valueRole: "value"
                                    currentIndex: root.hasViewModel ? (viewModel.commissionType === "cash_per_order" ? 1 : (viewModel.commissionType === "cash_per_contract" ? 2 : 0)) : 0
                                    background: Rectangle {
                                        color: "#181a26"
                                        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                                        radius: 4
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Text {
                                    text: "Mức hoa hồng"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                TextField {
                                    id: propCommissionValue
                                    objectName: "propCommissionValue"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    text: root.hasViewModel ? viewModel.commissionText : "0.1"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    background: Rectangle {
                                        color: "#181a26"
                                        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                                        radius: 4
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.preferredWidth: 140
                                spacing: 4
                                Text {
                                    text: "Trượt giá (Ticks)"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                SpinBox {
                                    id: propSlippageTicks
                                    objectName: "propSlippageTicks"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    from: 0
                                    to: 100
                                    value: root.hasViewModel ? viewModel.slippageTicks : 0
                                }
                            }
                        }
                    }

                    // Group 4: Đòn bẩy (Leverage) — BOT-105
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            Image {
                                source: "image://icons/settings/accent"
                                sourceSize: Qt.size(13, 13)
                            }
                            Text {
                                text: "ĐÒN BẨY (LEVERAGE)"
                                textFormat: Text.PlainText
                                color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme && Theme.border ? Theme.border : "#2a2d3e" }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Text {
                                    text: "Đòn bẩy Long (x)"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                SpinBox {
                                    id: propLongLeverage
                                    objectName: "propLongLeverage"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    from: 1
                                    to: 125
                                    value: root.hasViewModel ? viewModel.longLeverage : 1
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Text {
                                    text: "Đòn bẩy Short (x)"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                SpinBox {
                                    id: propShortLeverage
                                    objectName: "propShortLeverage"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    from: 1
                                    to: 125
                                    value: root.hasViewModel ? viewModel.shortLeverage : 1
                                }
                            }
                        }
                    }

                    // Group 5: Chốt lời tự động (Take Profit %) — BOT-041's
                    // broker-level TP had no UI path at all before EPIC-001A.
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            Image {
                                source: "image://icons/settings/accent"
                                sourceSize: Qt.size(13, 13)
                            }
                            Text {
                                text: "CHỐT LỜI TỰ ĐỘNG (TAKE PROFIT %)"
                                textFormat: Text.PlainText
                                color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme && Theme.border ? Theme.border : "#2a2d3e" }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            CheckBox {
                                id: propTakeProfitEnabled
                                objectName: "propTakeProfitEnabled"
                                text: "Bật Take Profit %"
                                checked: root.hasViewModel ? viewModel.takeProfitPctEnabled : false
                                contentItem: Text {
                                    text: propTakeProfitEnabled.text
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                    leftPadding: propTakeProfitEnabled.indicator.width + 6
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Text {
                                    text: "% Chốt lời (khớp take_profit_percent của strategy)"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    font.pixelSize: 11
                                }
                                TextField {
                                    id: propTakeProfitPct
                                    objectName: "propTakeProfitPct"
                                    Layout.fillWidth: true
                                    implicitHeight: 32
                                    enabled: propTakeProfitEnabled.checked
                                    text: root.hasViewModel ? viewModel.takeProfitPctText : "2.0"
                                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                    background: Rectangle {
                                        color: "#181a26"
                                        border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                                        radius: 4
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ==========================================
            // TAB 3: Định dạng (Style)
            // ==========================================
            ScrollView {
                clip: true
                ColumnLayout {
                    width: tabStack.width - 24
                    spacing: 12
                    Text {
                        text: "Hiển thị và màu sắc chỉ báo chiến lược (Sắp ra mắt)"
                        color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                        font.pixelSize: 12
                    }
                }
            }

            // ==========================================
            // TAB 4: Hiển thị (Visibility)
            // ==========================================
            ScrollView {
                clip: true
                ColumnLayout {
                    width: tabStack.width - 24
                    spacing: 12
                    Text {
                        text: "Bộ lọc hiển thị theo khung thời gian (Sắp ra mắt)"
                        color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                        font.pixelSize: 12
                    }
                }
            }
        }
    }

    footerData: [
        Button {
            id: btnResetProperties
            objectName: "btnResetBotParams"
            text: "Đặt lại mặc định"
            implicitHeight: 32
            background: Rectangle {
                color: "transparent"
                border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                radius: 6
            }
            contentItem: Text {
                text: parent.text
                color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            onClicked: root.resetAllFields()
        },

        Item { Layout.fillWidth: true },

        Button {
            id: btnPropertiesCancel
            objectName: "btnBotParamsCancel"
            text: "Hủy"
            implicitHeight: 32
            implicitWidth: 70
            background: Rectangle {
                color: parent.hovered ? "#2e3247" : "#242738"
                radius: 6
            }
            contentItem: Text {
                text: parent.text
                color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            onClicked: root.close()
        },

        Button {
            id: btnPropertiesSave
            objectName: "btnBotParamsSave"
            text: "Lưu & Chạy lại"
            implicitWidth: 150
            implicitHeight: 32
            background: Rectangle {
                color: parent.hovered ? "#ffd033" : (Theme && Theme.accent ? Theme.accent : "#f0b90b")
                radius: 6
            }
            contentItem: Text {
                text: parent.text
                color: "#000000"
                font.pixelSize: 11
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            onClicked: root.saveAndRerun()
        }
    ]

    function _collectFieldItems(item, result) {
        for (var i = 0; i < item.children.length; ++i) {
            var child = item.children[i]
            if (child.isBotParamField === true) {
                result.push(child)
            }
            _collectFieldItems(child, result)
        }
    }

    function resetAllFields() {
        var items = []
        _collectFieldItems(inputsColumn, items)
        for (var i = 0; i < items.length; ++i) {
            items[i].resetToDefault()
        }
        propInitialCapital.text = "10000"
        propCurrency.currentIndex = 0
        propOrderSizeType.currentIndex = 0
        propOrderSizeValue.text = "100"
        propPyramiding.value = 1
        propCommissionType.currentIndex = 0
        propCommissionValue.text = "0.1"
        propSlippageTicks.value = 0
        propLongLeverage.value = 1
        propShortLeverage.value = 1
        propTakeProfitEnabled.checked = false
        propTakeProfitPct.text = "2.0"
    }

    function saveAndRerun() {
        var items = []
        _collectFieldItems(inputsColumn, items)
        var inputValues = ({})
        for (var i = 0; i < items.length; ++i) {
            inputValues[items[i].fieldName] = items[i].currentValue
        }

        var brokerProps = {
            "initial_capital": propInitialCapital.text,
            "currency": propCurrency.currentText,
            "order_size_type": propOrderSizeType.currentValue,
            "order_size_text": propOrderSizeValue.text,
            "pyramiding": propPyramiding.value,
            "commission_type": propCommissionType.currentValue,
            "commission_text": propCommissionValue.text,
            "slippage_ticks": propSlippageTicks.value,
            "long_leverage": propLongLeverage.value,
            "short_leverage": propShortLeverage.value,
            "take_profit_enabled": propTakeProfitEnabled.checked,
            "take_profit_pct_text": propTakeProfitPct.text
        }

        viewModel.requestStrategyPropertiesSave({
            "inputs": inputValues,
            "properties": brokerProps
        })
    }
}
