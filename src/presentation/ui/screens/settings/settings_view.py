from pathlib import Path

from sagittarius_engine.extensions.pyside_mvc import QmlHostView


class SettingsView(QmlHostView):
    """
    @brief The View for the API & Credentials screen — QML-rendered.

    @details
    A thin QmlHostView subclass: all layout and styling live in
    SettingsScreen.qml, all state in SettingsViewModel. The Presenter owns
    the wiring (see settings_presenter.py), which is why this class carries
    no logic of its own beyond pointing at its QML directory.
    """

    QML_DIR = Path(__file__).parent
