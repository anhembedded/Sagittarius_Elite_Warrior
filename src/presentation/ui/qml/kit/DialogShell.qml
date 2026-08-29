import QtQuick
import QtQuick.Layouts

// Shared dialog shell — header (accent mark + title + close) + one body +
// optional footer (Hủy + confirm). Design spec 2026-08-30: "Was: every
// picker had its own header, padding and footer arrangement."
//
// For a fully-QML host (qml-rule.md §0.1's second row): a screen still
// hosted by QtWidgets uses `QmlOverlay` for its chrome, same as
// `SelectList`/`StatGrid`/`CheckboxList`/`Capital` today — this shell is
// for the day a whole route is QML and a modal has nothing QtWidgets to
// borrow chrome from.
ColumnLayout {
    id: root
    objectName: "dialogShell"
    spacing: 14

    property string title: ""
    property bool showFooter: false
    property string cancelText: "Hủy"
    property string confirmText: "Áp dụng"
    property bool confirmEnabled: true
    default property alias body: bodyItem.data
    signal cancelled()
    signal confirmed()

    PanelHeader {
        Layout.fillWidth: true
        title: root.title

        Button {
            objectName: "btnDialogShellClose"
            text: "×"
            role: "ghost"
            onClicked: root.cancelled()
        }
    }

    Item {
        id: bodyItem
        objectName: "dialogShellBody"
        Layout.fillWidth: true
        Layout.fillHeight: true
    }

    RowLayout {
        objectName: "dialogShellFooter"
        Layout.fillWidth: true
        visible: root.showFooter

        Item { Layout.fillWidth: true }
        Button {
            objectName: "btnDialogShellCancel"
            text: root.cancelText
            role: "secondary"
            onClicked: root.cancelled()
        }
        Button {
            objectName: "btnDialogShellConfirm"
            text: root.confirmText
            role: "primary"
            enabled: root.confirmEnabled
            onClicked: root.confirmed()
        }
    }
}
