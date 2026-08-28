import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QMetaObject, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtTest import QTest

class VM(QObject):
    symbolChanged = Signal()
    def __init__(self):
        super().__init__(); self._s = "BTCUSDT"
    def _get(self): return self._s
    def _set(self, v):
        if v != self._s:
            self._s = v; self.symbolChanged.emit()
    symbol = Property(str, _get, _set, notify=symbolChanged)

app = QApplication([])
vm = VM()
w = QQuickWidget(); w.rootContext().setContextProperty("vm", vm)
w.setSource(QUrl.fromLocalFile("Probe.qml")); w.show(); app.processEvents()
root = w.rootObject()
field = root.findChild(QObject, "txtSymbol")

print("--- 4a. setProperty + emit the real (no-arg) signal ---")
field.setProperty("text", "SOLUSDT")
QMetaObject.invokeMethod(field, "textEdited", Qt.ConnectionType.DirectConnection)
app.processEvents()
print("vm.symbol =", repr(vm.symbol), "->", "OK" if vm.symbol == "SOLUSDT" else "FAIL")

print("\n--- 4b. real keyboard typing through QTest (closest to a user) ---")
vm.symbol = "BTCUSDT"; app.processEvents()
field.setProperty("focus", True); app.processEvents()
QTest.keyClicks(w, "XX")
app.processEvents()
print("after QTest.keyClicks('XX'): field.text =", repr(field.property("text")),
      "| vm.symbol =", repr(vm.symbol))
