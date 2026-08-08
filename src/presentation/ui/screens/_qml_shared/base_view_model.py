from PySide6.QtCore import Property, QObject, Signal


class BaseQmlViewModel(QObject):
    """
    @brief Base for every QML screen's ViewModel: carries the FSM-driven
    `uiMode` property QML binds its enabled/visible states to.

    @details
    QmlHostView.apply_ui_mode() (fed by BasePresenter's FSM binding) calls
    `set_ui_mode()` here; QML reads `viewModel.uiMode` — e.g.
    `enabled: viewModel.uiMode !== "LOCKED"`. This replaces the
    reflection-over-ui_matrix.json mechanism (UIMatrixMixin) used by the
    QtWidgets screens: QML binds declaratively, so a JSON matrix mapping
    widget-attribute names to booleans has nothing to drive.
    """

    uiModeChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ui_mode = "IDLE"

    def _get_ui_mode(self) -> str:
        return self._ui_mode

    uiMode = Property(str, _get_ui_mode, notify=uiModeChanged)

    def set_ui_mode(self, mode: str) -> None:
        if mode == self._ui_mode:
            return
        self._ui_mode = mode
        self.uiModeChanged.emit()
