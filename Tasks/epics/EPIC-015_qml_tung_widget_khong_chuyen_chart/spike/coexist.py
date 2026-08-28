import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, QUrl, Property, Signal
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QStackedWidget, QDialog
from PySide6.QtQuickWidgets import QQuickWidget

app = QApplication([])
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml, get_theme_bridge
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette, get_icon_loader
configure_app_qml(Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict())
get_theme_bridge(Palette.as_ui_dict())
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_card import ChartCard

class VM(QObject):
    symbolChanged = Signal()
    def __init__(self): super().__init__(); self._s = "BTCUSDT"
    symbol = Property(str, lambda s: s._s, notify=symbolChanged)

vm = VM()

print("=== A. QML panel as a SIBLING of the pyqtgraph chart, same layout ===")
screen = QWidget(); lay = QVBoxLayout(screen)
qml_panel = QQuickWidget()
qml_panel.rootContext().setContextProperty("vm", vm)
qml_panel.setSource(QUrl.fromLocalFile("Probe.qml"))
qml_panel.setFixedHeight(140)
chart = ChartCard("BTCUSDT")
lay.addWidget(qml_panel)        # QML top panel
lay.addWidget(chart, 1)         # QtWidgets/pyqtgraph chart below
screen.resize(900, 600); screen.show(); app.processEvents()
print("qml status:", qml_panel.status(), "| qml visible:", qml_panel.isVisible(),
      "geom:", qml_panel.geometry())
print("chart visible:", chart.isVisible(), "geom:", chart.geometry())
print("qml root found:", qml_panel.rootObject() is not None,
      "| label reads VM:", repr(qml_panel.rootObject().findChild(QObject,"lblEcho").property("text")))

print("\n=== B. QQuickWidget as a whole route inside the app's QStackedWidget ===")
stack = QStackedWidget()
w_screen = QWidget()                       # an existing QtWidgets screen
q_screen = QQuickWidget()                  # a migrated QML screen
q_screen.rootContext().setContextProperty("vm", vm)
q_screen.setSource(QUrl.fromLocalFile("Probe.qml"))
stack.addWidget(w_screen); stack.addWidget(q_screen)
stack.resize(900, 600); stack.show()
stack.setCurrentIndex(1); app.processEvents()
print("route switched to QML screen:", stack.currentWidget() is q_screen,
      "| status:", q_screen.status(), "| visible:", q_screen.isVisible())
stack.setCurrentIndex(0); app.processEvents()
print("switched back to widget screen:", stack.currentWidget() is w_screen)

print("\n=== C. QML modal as its own QDialog (tier 0) ===")
dlg = QDialog(); dl = QVBoxLayout(dlg)
qm = QQuickWidget(); qm.rootContext().setContextProperty("vm", vm)
qm.setSource(QUrl.fromLocalFile("Probe.qml")); dl.addWidget(qm)
dlg.setModal(True); dlg.show(); app.processEvents()
print("modal shown:", dlg.isVisible(), "| qml inside status:", qm.status())
dlg.close()
