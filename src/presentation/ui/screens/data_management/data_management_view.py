from pathlib import Path

from sagittarius_engine.extensions.pyside_mvc import QmlHostView


class DataManagementView(QmlHostView):
    """
    @brief The View for the Database screen — QML-rendered.

    @details
    A thin QmlHostView subclass: layout/styling live in DatabaseScreen.qml,
    state in DataManagementViewModel, and orchestration in
    DataManagementPresenter. FSM state reaches the QML through
    QmlHostView.apply_ui_mode -> the view model's `uiMode` property, which
    the QML binds its `enabled:` states to (replacing the ui_matrix.json
    reflection the QtWidgets version used).
    """

    QML_DIR = Path(__file__).parent
