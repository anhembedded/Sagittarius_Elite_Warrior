"""Widget-ViewModel test WITHOUT any QApplication, QML, or GUI at all."""
import os
os.environ["QT_QPA_PLATFORM"] = "minimal"
from PySide6.QtCore import QObject, Property, Signal, Slot

class SymbolPickerVM(QObject):
    """State + rules of the picker. QML will be a dumb shell over this."""
    queryChanged = Signal()
    resultsChanged = Signal()
    symbolChosen = Signal(str)

    def __init__(self, symbols):
        super().__init__(); self._all = list(symbols); self._q = ""
    def _get_q(self): return self._q
    def _set_q(self, v):
        if v != self._q:
            self._q = v; self.queryChanged.emit(); self.resultsChanged.emit()
    query = Property(str, _get_q, _set_q, notify=queryChanged)

    @Property("QStringList", notify=resultsChanged)
    def results(self):
        q = self._q.upper()
        return [s for s in self._all if not q or q in s]

    @Slot(str)
    def choose(self, symbol): self.symbolChosen.emit(symbol)

# --- a plain pytest-style test: NO QApplication constructed anywhere ---
vm = SymbolPickerVM(["BTCUSDT", "ETHUSDT", "ETHBTC"])
assert vm.results == ["BTCUSDT", "ETHUSDT", "ETHBTC"]

vm.query = "eth"
assert vm.results == ["ETHUSDT", "ETHBTC"], vm.results

fired = []
vm.symbolChosen.connect(fired.append)
vm.choose("ETHBTC")
assert fired == ["ETHBTC"], fired

from PySide6.QtWidgets import QApplication
print("QApplication instance during the whole test:", QApplication.instance())
print("ALL ASSERTIONS PASSED — widget ViewModel testable with zero GUI")
