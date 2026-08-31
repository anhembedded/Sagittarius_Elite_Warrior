import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Standalone modal component. The host supplies `vm` and `theme` root
// properties; there is no dependency on QmlOverlay, Palette, or an app
// screen. State and filtering remain in SymbolPickerVM.
//
// The file's top-level Item is a thin, invisible host. `QQuickWidget`
// requires its root object to be an `Item`; `Popup` is not one, so it can
// only be declared as a child, never as the file's own root. The real modal
// is `pickerPopup` below — its `modal`/`closePolicy` properties supply the
// dim backdrop, Escape-to-close, and click-outside-to-close this component
// used to hand-roll by hand (see `.agents/rules/qml-rule.md` §0.1).
Item {
    id: root
    anchors.fill: parent
    implicitWidth: 720
    implicitHeight: 620

    property var vm: typeof symbolPickerPreviewVM !== "undefined" && symbolPickerPreviewVM ? symbolPickerPreviewVM : fallbackVM
    property var theme: typeof symbolPickerPreviewTheme !== "undefined" && symbolPickerPreviewTheme ? symbolPickerPreviewTheme : fallbackTheme

    signal symbolChosen(string symbol)
    signal dismissed()

    QtObject {
        id: fallbackVM
        property string query: ""
        property var scopeTabs: []
        property var quoteTabs: []
        property var favouriteModel: []
        property var resultModel: []
        property var favouriteRows: []
        property var resultRows: []
        property var rows: []
        property int resultCount: 0
        property string statusMessage: ""
        property string currentSymbol: ""
        property bool showSplit: false
        signal symbolChosen(string symbol)
        function reset() {}
        function setQuery(value) {}
        function setScope(value) {}
        function setQuote(value) {}
        function moveFocus(step) {}
        function chooseFocused() {}
        function choose(symbol) {}
        function toggleFavourite(symbol) {}
        function requestRefresh() {}
    }

    QtObject {
        id: fallbackTheme
        property color bg: "transparent"
        property color bgCard: "transparent"
        property color bgCardHeader: "transparent"
        property color border: "transparent"
        property color textPrimary: "transparent"
        property color accent: "transparent"
        property color muted: "transparent"
        property color stateHoverBg: "transparent"
        property color stateActiveTint: "transparent"
        property color stateNavBorder: "transparent"
    }

    function openPicker() {
        root.vm.reset()
        pickerPopup.open()
    }

    function closePicker() {
        pickerPopup.close()
    }

    function handleNavigation(key) {
        if (key === Qt.Key_Down) {
            root.vm.moveFocus(1)
            return true
        }
        if (key === Qt.Key_Up) {
            root.vm.moveFocus(-1)
            return true
        }
        if (key === Qt.Key_Return || key === Qt.Key_Enter) {
            root.vm.chooseFocused()
            return true
        }
        return false
    }

    Connections {
        target: root.vm
        function onSymbolChosen(symbol) {
            root.symbolChosen(symbol)
            pickerPopup.close()
        }
    }

    Popup {
        id: pickerPopup
        objectName: "symbolPicker"
        modal: true
        focus: true
        padding: 12
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        anchors.centerIn: Overlay.overlay
        width: Math.min(Overlay.overlay ? Overlay.overlay.width - 16 : 720, 720)
        height: Math.min(Overlay.overlay ? Overlay.overlay.height - 16 : 620, 620)

        onOpened: searchField.forceActiveFocus()
        onClosed: root.dismissed()

        Overlay.modal: Rectangle {
            color: root.theme.bg
            opacity: 0.82
        }

        background: Rectangle {
            color: root.theme.bgCard
            border.width: 1
            border.color: root.theme.border
            radius: 8
        }

        contentItem: ColumnLayout {
            // BUG-070: `Keys` is only valid on a `QQuickItem` — `Popup`
            // itself derives from `QQuickPopup` (a plain `QObject`), not
            // `Item`, so attaching it there (as this used to) makes Qt Quick
            // print "Could not attach Keys property to: ... is not an Item"
            // every time the popup opens. `contentItem` IS an `Item`
            // (`ColumnLayout` extends it), and unhandled key events bubble
            // up the visual parent chain the same way, so this is a
            // same-behavior move, not a functional change: `searchField`'s
            // own `Keys.onPressed` below still fires first since it holds
            // active focus (`onOpened: searchField.forceActiveFocus()`);
            // this stays as the fallback for anything else in the popup
            // that doesn't handle Up/Down/Enter itself.
            Keys.onPressed: function(event) {
                if (root.handleNavigation(event.key)) event.accepted = true
            }

            width: pickerPopup.availableWidth
            height: pickerPopup.availableHeight
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Rectangle { width: 2; height: 14; color: root.theme.accent }
                Text {
                    objectName: "symbolPickerTitle"
                    Layout.fillWidth: true
                    text: "CHỌN SYMBOL"
                    textFormat: Text.PlainText
                    color: root.theme.textPrimary
                    font.bold: true
                    font.pixelSize: 12
                    font.letterSpacing: 0.8
                }
                ToolButton {
                    objectName: "btnRefreshSymbols"
                    text: "🔄"
                    ToolTip.visible: hovered
                    ToolTip.text: "Cập nhật danh sách từ sàn Binance"
                    onClicked: root.vm.requestRefresh()
                    contentItem: Text {
                        text: parent.text
                        textFormat: Text.PlainText
                        color: root.theme.muted
                        font.pixelSize: 14
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: "transparent" }
                }
                ToolButton {
                    objectName: "btnCloseSymbolPicker"
                    text: "×"
                    onClicked: root.closePicker()
                    contentItem: Text {
                        text: parent.text
                        textFormat: Text.PlainText
                        color: root.theme.muted
                        font.pixelSize: 18
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: "transparent" }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: root.theme.border }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: searchField
                    objectName: "txtSymbolSearch"
                    Layout.fillWidth: true
                    placeholderText: "Tìm symbol (vd: BTC)"
                    text: root.vm.query
                    color: root.theme.textPrimary
                    selectByMouse: true
                    onTextEdited: root.vm.setQuery(text)
                    Keys.onPressed: function(event) {
                        if (root.handleNavigation(event.key)) event.accepted = true
                    }
                    background: Rectangle {
                        color: root.theme.bg
                        border.width: 1
                        border.color: searchField.activeFocus ? root.theme.accent : root.theme.stateNavBorder
                        radius: 6
                    }
                }
                Text {
                    objectName: "lblSymbolResultCount"
                    text: root.vm.resultCount + " kết quả"
                    textFormat: Text.PlainText
                    color: root.theme.muted
                    font.pixelSize: 11
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Row {
                    objectName: "tabsSymbolScope"
                    spacing: 2
                    Repeater {
                        model: root.vm.scopeTabs
                        SymbolPickerTab {
                            tabData: modelData
                            theme: root.theme
                            onActivated: root.vm.setScope(tabId)
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                Row {
                    objectName: "tabsSymbolQuote"
                    spacing: 2
                    Repeater {
                        model: root.vm.quoteTabs
                        SymbolPickerTab {
                            tabData: modelData
                            theme: root.theme
                            onActivated: root.vm.setQuote(tabId)
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: root.theme.border }

            ScrollView {
                id: resultScroll
                objectName: "symbolPickerResults"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                Column {
                    id: resultColumn
                    width: resultScroll.availableWidth
                    spacing: 8
                    Text {
                        objectName: "lblSymbolStatus"
                        width: parent.width
                        visible: root.vm.statusMessage !== ""
                        text: root.vm.statusMessage
                        textFormat: Text.PlainText
                        color: root.theme.muted
                        font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter
                    }
                    Text {
                        objectName: "lblSymbolFavouritesHeading"
                        width: parent.width
                        visible: root.vm.showSplit
                        text: "YÊU THÍCH"
                        textFormat: Text.PlainText
                        color: root.theme.muted
                        font.bold: true
                        font.pixelSize: 10
                        font.letterSpacing: 0.8
                    }
                    GridView {
                        id: favouriteGrid
                        objectName: "symbolFavouriteGrid"
                        width: parent.width
                        height: Math.min(Math.max(contentHeight, 1), 140)
                        cellWidth: Math.max(1, (width - 16) / 3)
                        cellHeight: 66
                        reuseItems: true
                        clip: true
                        visible: root.vm.showSplit
                        model: root.vm.favouriteModel
                        delegate: SymbolPickerCard {
                            symbol: model.symbol
                            base: model.base
                            quote: model.quote
                            subtitle: model.subtitle
                            favourite: model.favourite
                            current: model.current
                            focused: model.focused
                            vm: root.vm
                            theme: root.theme
                        }
                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                        }
                    }
                    Text {
                        objectName: "lblSymbolResultsHeading"
                        width: parent.width
                        visible: root.vm.showSplit && root.vm.resultModel.count > 0
                        text: "TẤT CẢ KẾT QUẢ"
                        textFormat: Text.PlainText
                        color: root.theme.muted
                        font.bold: true
                        font.pixelSize: 10
                        font.letterSpacing: 0.8
                    }
                    GridView {
                        id: resultGrid
                        objectName: "symbolResultGrid"
                        width: parent.width
                        height: Math.min(Math.max(contentHeight, 1), 220)
                        cellWidth: Math.max(1, (width - 16) / 3)
                        cellHeight: 66
                        reuseItems: true
                        clip: true
                        model: root.vm.resultModel
                        delegate: SymbolPickerCard {
                            symbol: model.symbol
                            base: model.base
                            quote: model.quote
                            subtitle: model.subtitle
                            favourite: model.favourite
                            current: model.current
                            focused: model.focused
                            vm: root.vm
                            theme: root.theme
                        }
                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: root.theme.border }
            RowLayout {
                Layout.fillWidth: true
                Text {
                    objectName: "lblSymbolKeyHints"
                    Layout.fillWidth: true
                    text: "↑↓ di chuyển   ↵ chọn   ☆ yêu thích"
                    textFormat: Text.PlainText
                    color: root.theme.muted
                    font.pixelSize: 10
                }
                Text {
                    objectName: "lblSymbolCurrent"
                    text: "Đang dùng: " + root.vm.currentSymbol
                    textFormat: Text.PlainText
                    color: root.theme.muted
                    font.pixelSize: 10
                }
            }
        }
    }
}
