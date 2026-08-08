from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QVBoxLayout

from sagittarius_engine.extensions.pyside_mvc import BaseView

from .icon_image_provider import ICON_PROVIDER_ID, IconImageProvider
from .qml_style import ensure_qml_style
from .theme_bridge import register_theme


def create_quick_widget() -> QQuickWidget:
    """
    @brief Builds a QQuickWidget wired with this app's shared QML plumbing —
    the "Basic" style, the `Theme` singleton, and the icon provider.

    @details
    Every QML-hosting widget needs this setup, whether it's the sole widget
    of a QmlHostView (one QML screen per View) or, like the Dev Board's
    hybrid QSplitter layout, one of several widgets sharing a single View
    alongside a QtWidgets ChartCard. Factored out so both paths configure
    identically instead of the hybrid case hand-rolling a partial copy.
    """
    ensure_qml_style()
    quick_widget = QQuickWidget()
    quick_widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    register_theme(quick_widget)
    # Engine takes ownership of the provider, so each QQuickWidget gets its
    # own instance; the underlying IconLoader it delegates to is the shared
    # app-wide singleton, so the icon cache is still not duplicated.
    quick_widget.engine().addImageProvider(ICON_PROVIDER_ID, IconImageProvider())
    return quick_widget


class QmlHostView(BaseView):
    """
    @brief Base class for every QML-backed screen: hosts a QQuickWidget,
    wires the shared `Theme` singleton, and bridges BasePresenter's FSM
    state into a QML-bindable property.

    @details
    Being a QWidget subclass is what lets PresenterManager keep routing
    these screens with zero changes (`stacked_widget.addWidget(view)` —
    verified in BOT-028).

    Ordering contract: `setSource()` is deliberately NOT called in
    __init__ — a Presenter must register its ViewModel as a context
    property *before* `load_qml()`, or QML resolves that name to undefined
    at parse time. Subclass presenters call:
        view.set_view_model(vm)   # optional, screen-specific
        view.load_qml("screen.qml")

    FSM binding: BasePresenter._bind_fsm_to_ui duck-types
    `view.apply_ui_mode(mode, section_key)` (falling back to it when the
    view has no `control_card`), so overriding it here is enough to route
    FSM state into QML — no changes to the shared pyside_mvc package.
    Screens expose it to QML as a `uiMode` string property on their
    ViewModel, which QML binds to directly (e.g.
    `enabled: viewModel.uiMode !== "LOCKED"`), replacing the
    reflection-based ui_matrix.json mechanism used by the Widgets screens.
    """

    #: Subclasses set this to the directory holding their .qml files.
    QML_DIR: Path = Path(__file__).parent

    def __init__(self, parent=None):
        super().__init__(parent)

        self.quick_widget = create_quick_widget()
        self._view_model = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.quick_widget)

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Registers a screen's ViewModel as a QML context property. Must be
        called before load_qml() — see the ordering contract above."""
        self._view_model = view_model
        self.quick_widget.rootContext().setContextProperty(context_name, view_model)

    def load_qml(self, qml_filename: str) -> None:
        """Loads a QML document by filename, relative to the subclass's QML_DIR."""
        qml_path = self.QML_DIR / qml_filename
        self.quick_widget.setSource(QUrl.fromLocalFile(str(qml_path)))

    def apply_ui_mode(self, mode, section_key: str = "main") -> None:
        """
        @brief Receives FSM state changes from BasePresenter and forwards them
        to the ViewModel's `uiMode` property for QML to bind against.
        @param mode A UIMode enum member or plain string; normalized to its
        string value (BasePresenter passes the enum, tests may pass either).
        @param section_key Accepted for signature compatibility with
        UIMatrixMixin.apply_ui_mode; unused here — QML screens bind their own
        controls directly instead of consulting a per-section JSON matrix.
        """
        if self._view_model is None:
            return
        mode_value = getattr(mode, "value", mode)
        self._view_model.set_ui_mode(str(mode_value))
