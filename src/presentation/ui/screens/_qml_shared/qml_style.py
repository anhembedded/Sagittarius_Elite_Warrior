from PySide6.QtQuickControls2 import QQuickStyle

# "Basic" is the neutral, fully-customizable Qt Quick Controls style.
#
# The platform default on Windows is the native "Windows" style, which
# SILENTLY IGNORES `background:` / `contentItem:` overrides — it only logs a
# "current style does not support customization of this control" warning and
# renders the native chrome instead. Every custom-styled Button/TextField/
# SpinBox in this app's QML depends on those overrides, so the app-wide style
# must be pinned to a customizable one before any QML is loaded.
_CUSTOMIZABLE_STYLE = "Basic"


def ensure_qml_style() -> None:
    """
    @brief Pins the Qt Quick Controls style to a customizable one, once.

    @details
    QQuickStyle.setStyle() only takes effect before the first QML component
    is loaded, so this is called from QmlHostView's constructor rather than
    only at app startup — that way screens instantiated directly (e.g. in
    unit tests, which never run app_bootstrapper) get the same styling as
    the real app, instead of tests passing against native chrome the user
    would never see.
    """
    if QQuickStyle.name() != _CUSTOMIZABLE_STYLE:
        QQuickStyle.setStyle(_CUSTOMIZABLE_STYLE)
