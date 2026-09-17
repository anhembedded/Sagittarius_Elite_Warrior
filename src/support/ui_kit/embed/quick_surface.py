"""`QuickSurface` — the one way this app embeds a QML scene in QtWidgets.

@par Why one abstraction, not a convention
`BUG-115`: ten hosts each hand-built a `QQuickWidget` with the same twelve
lines — style pin, `Theme` context, context-object lifetime, load-or-raise,
resize mode — and the same comment, *"transparent so the parent SURFACE shows
through"*. That assumption is only true on the software rendering path
(`offscreen`, `widget.grab()`, i.e. every headless test). On every real
desktop session a `QQuickWidget` is a render-to-texture widget: Qt punches a
hole in the widget backing store under it and composites the scene over a
black (X11) or see-through (Wayland) clear — the parent's background is not
there to show. Ten modal bodies and inline tables shipped black or
see-through behind a green suite, because nothing enforced the contract and
each copy could drift. This class is the contract, in one place:

- **The scene is opaque, and its background is the token of the `StyleRole`
  it is embedded in** — the same rule a child `QWidget` on a `QFrame` obeys.
  The token comes from `kit.style.background_token(role)`, the same table
  `apply_role()` paints the parent from, so the two painters cannot disagree.
  The engine's `create_quick_widget()` owns *that* the clear colour is opaque
  (`TASK-042`); this class owns *which* token, because `StyleRole` is this
  app's vocabulary and the engine must not know it.
- **The engine's factory is the only place a `QQuickWidget` is constructed**
  (`create_quick_widget()`: Basic style, `Theme`, icon provider, import
  path). This class composes it rather than subclassing `QQuickWidget`, so no
  file in this app constructs or inherits one — `test_quick_widget_only_in_embed.py`
  guards that.
- Context objects are held here for as long as the scene can read them
  (`qml-rule.md` §1.1); a `.qml` that fails to load raises instead of
  rendering a blank box (`qml-rule.md` §7); `root_object` is the one name
  every host and test reaches the scene through.

@par Two host shapes, one class
A host that *is* a `QWidget` in a layout (a `Panel` body, an `Overlay` body,
a `QDialog` body) composes a `QuickSurface`. A host whose public surface is
the QML scene itself (`ProgressBannerWidget`, `StatusPillWidget`,
`StatCardRowWidget`, `ChartToolbar`) subclasses it — its callers only ever
used setters and signals, never `QQuickWidget` API, so nothing above them
changes.

@par No host of either shape is left
`EPIC-025` PR 4.3l deleted the last `.qml` under `src/` (ADR D21), and with
it every class named above. This package still loads and is still tested, but
the only thing that constructs a `QuickSurface` now is
`scripts/quick_surface_desktop_probe.py` — the manual probe `BUG-115` left
behind, which is a real reason to keep the contract working and not a reason
to keep the package. It is PR 4.4's to remove, together with the theme layer
(`theme_bootstrap`, `configure_app_qml`, `Palette`, `kit/style.py`), which
still has many live consumers and which HLD §11.4 retires in the same step.
Deleted here instead: `support/ui_kit/qml_overlay.py`, whose whole purpose
was a modal with a `.qml` body, so it can never have a consumer again.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import QObject, QSize, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.style import (
    StyleRole,
    background_token,
)
from sagittarius_engine.extensions.pyside_mvc import create_quick_widget

from .size_policy import QuickSizePolicy


class QuickSurface(QWidget):  # base-exempt: a transparent holder, not a surface
    # (it paints nothing itself — the embedded Quick scene clears to the
    # `surface` role's own token, and the QtWidgets surface it sits on is
    # whatever `Panel`/`Overlay`/`Card` painted around it)
    """
    @brief A QML scene embedded on a known `StyleRole` surface.

    @param qml_file Absolute path of the `.qml` to load.
    @param surface The role of the QtWidgets surface this scene sits on. Its
        background token becomes the scene's opaque clear colour.
    @param context Values exposed to QML as context properties (the widget
        ViewModel under `vm`, a plain list a preview binds to, ...). Held for
        this widget's lifetime — a context property is a borrowed reference.
        `Theme` is installed by the engine factory and needs no entry here.
    @param size_policy `FILL` (the default) or `HUG` — see `QuickSizePolicy`.
    @param object_name Set on the inner `QQuickWidget`, the object tests and
        `QTest` clicks address (`qml-rule.md` §5.4).
    @raise RuntimeError If the `.qml` fails to load — with Qt's own error
        list, once, instead of an empty rectangle.
    """

    def __init__(
        self,
        qml_file: Path,
        *,
        surface: StyleRole = StyleRole.SURFACE,
        context: Mapping[str, object] | None = None,
        size_policy: QuickSizePolicy = QuickSizePolicy.FILL,
        object_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._surface_role = surface
        self._size_policy = size_policy
        # A QML context property is a borrowed pointer; Python must keep the
        # object alive for as long as the scene can read it.
        self._context: dict[str, object] = dict(context or {})

        self._quick = create_quick_widget(background=background_token(surface))
        self._quick.setResizeMode(size_policy.value)
        if object_name:
            self._quick.setObjectName(object_name)
        root_context = self._quick.rootContext()
        for name, obj in self._context.items():
            root_context.setContextProperty(name, obj)

        self._quick.setSource(QUrl.fromLocalFile(str(qml_file)))
        if self._quick.status() is not QQuickWidget.Status.Ready:
            raise RuntimeError(
                f"QML failed to load: {qml_file}\n"
                + "\n".join(error.toString() for error in self._quick.errors())
            )
        root = self._quick.rootObject()
        if root is None:  # pragma: no cover - status check above already raises
            raise RuntimeError(f"QML root object is missing: {qml_file}")
        self._root = root

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._quick)
        if size_policy is QuickSizePolicy.HUG:
            # Hug the scene: never let a parent layout stretch this widget
            # past the root's own implicit size, in either direction.
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    @property
    def root_object(self) -> QObject:
        """The loaded QML root — `findChild`/`qml_item` into it by `objectName`."""
        return self._root

    @property
    def quick_widget(self) -> QQuickWidget:
        """The inner widget, for `QTest` input that needs a `QWidget` target."""
        return self._quick

    @property
    def surface_role(self) -> StyleRole:
        """The role this scene was declared to sit on."""
        return self._surface_role

    def sizeHint(self) -> QSize:
        # Under `HUG` the inner widget's hint is the QML root's implicit
        # size; under `FILL` it is whatever Qt reports, and the layout above
        # decides anyway.
        return self._quick.sizeHint()

    def minimumSizeHint(self) -> QSize:
        if self._size_policy is QuickSizePolicy.HUG:
            return self._quick.sizeHint()
        return super().minimumSizeHint()
