import sys
from unittest.mock import MagicMock

class MockQWidget:
    def __init__(self, *args, **kwargs):
        pass

class MockSignal:
    def __init__(self, *args, **kwargs):
        pass
    def connect(self, *args, **kwargs):
        pass
    def emit(self, *args, **kwargs):
        pass

def mock_slot(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

# Create mock modules
pyside_mock = MagicMock()
qtcore_mock = MagicMock()
qtwidgets_mock = MagicMock()
qtgui_mock = MagicMock()
pyqtgraph_mock = MagicMock()

# Inject specific classes/functions
qtwidgets_mock.QWidget = MockQWidget
qtwidgets_mock.QApplication = MagicMock
qtwidgets_mock.QApplication.instance = MagicMock(return_value=MagicMock())
qtcore_mock.Signal = MockSignal
qtcore_mock.Slot = mock_slot
qtcore_mock.QDateTime = MagicMock
qtcore_mock.QTimer = MagicMock
pyqtgraph_mock.PlotWidget = MockQWidget

sys.modules['PySide6'] = pyside_mock
sys.modules['PySide6.QtCore'] = qtcore_mock
sys.modules['PySide6.QtWidgets'] = qtwidgets_mock
sys.modules['PySide6.QtGui'] = qtgui_mock
sys.modules['pyqtgraph'] = pyqtgraph_mock

