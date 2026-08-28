import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 320; height: 140
    color: "#151823"

    Column {
        spacing: 8
        TextField {
            objectName: "txtSymbol"
            text: vm.symbol                  // binding: VM -> UI
            onTextEdited: vm.symbol = text   // binding: UI -> VM
        }
        Text {
            objectName: "lblEcho"
            color: "white"
            text: "Đang dùng: " + vm.symbol  // reactive, no Python glue
        }
        Button {
            objectName: "btnPick"
            text: "Chọn"
            onClicked: vm.requestPick()
        }
    }
}
