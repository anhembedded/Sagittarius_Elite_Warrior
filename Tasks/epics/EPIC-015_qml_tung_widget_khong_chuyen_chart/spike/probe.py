import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QMetaObject, Qt, Q_ARG
from PySide6.QtWidgets import QApplication
from PySide6.QtQuickWidgets import QQuickWidget

class VM(QObject):
    symbolChanged = Signal()
    pickRequested = Signal()
    def __init__(self):
        super().__init__(); self._s = "BTCUSDT"
    def _get(self): return self._s
    def _set(self, v):
        if v != self._s:
            self._s = v; self.symbolChanged.emit()
    symbol = Property(str, _get, _set, notify=symbolChanged)
    @Slot()
    def requestPick(self): self.pickRequested.emit()

app = QApplication([])
vm = VM()
w = QQuickWidget()
w.rootContext().setContextProperty("vm", vm)
w.setSource(QUrl.fromLocalFile("Probe.qml"))
w.show(); app.processEvents()
print("status:", w.status(), "errors:", [e.toString() for e in w.errors()])

root = w.rootObject()
print("\n--- 1. findChild by objectName from Python ---")
field = root.findChild(QObject, "txtSymbol")
label = root.findChild(QObject, "lblEcho")
btn   = root.findChild(QObject, "btnPick")
print("found:", field is not None, label is not None, btn is not None)

print("\n--- 2. read a QML property from Python ---")
print("field.text =", repr(field.property("text")))
print("label.text =", repr(label.property("text")))

print("\n--- 3. VM -> UI binding (no glue code at all) ---")
vm.symbol = "ETHBTC"; app.processEvents()
print("after vm.symbol='ETHBTC':  field.text =", repr(field.property("text")),
      "| label.text =", repr(label.property("text")))

print("\n--- 4. UI -> VM binding: simulate the user typing ---")
field.setProperty("text", "SOLUSDT")
QMetaObject.invokeMethod(field, "textEdited", Qt.ConnectionType.DirectConnection, Q_ARG(str, "SOLUSDT"))
app.processEvents()
print("after typing 'SOLUSDT':    vm.symbol =", repr(vm.symbol))

print("\n--- 5. click a QML button from Python, assert the VM signal ---")
got = []
vm.pickRequested.connect(lambda: got.append(True))
QMetaObject.invokeMethod(btn, "clicked", Qt.ConnectionType.DirectConnection)
app.processEvents()
print("vm.pickRequested fired:", got == [True])
