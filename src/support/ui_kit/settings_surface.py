"""The Settings surface: one form section per contributing module (`EPIC-025` PR 4.4e).

Not a `WorkbenchSurface`: a settings screen is a stack of forms, not a
workbench of dockable panels around a central chart — `architecture-rule.md`
§5 keeps the two apart because forcing `SETTINGS_SECTION` into
`WorkbenchSurface.place_widget()` would put a fourth, structurally different
rendering strategy behind the same `elif` chain that today only ever branches
on "which dock area" (`workbench_surface.py`'s own table). `Surface("settings",
accepts={Place.SETTINGS_SECTION})` still owns the policy; this owns the one
place it accepts.

@par Why `typing.Protocol`, not an ABC — same reason `WorkbenchSurface` gives
This class is a `QWidget`, so it is a `QObject` subclass, and `ABCMeta`
conflicts with Shiboken's metaclass (`architecture-rule.md` §2.1 reason (a)).
`IPlaceHost` is `@runtime_checkable`, so `isinstance()` still holds without
inheriting it.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import PreferredHeightScrollArea


class SettingsSurface(QWidget):  # base-exempt: ADR D20-22, plain container
    """A scrollable stack of `QGroupBox` sections, one per contribution."""

    def __init__(self, surface: Surface, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._surface = surface
        self.setObjectName(f"surface::{surface.surface_id}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = PreferredHeightScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        self._sections_layout = QVBoxLayout(content)
        self._sections_layout.setContentsMargins(20, 20, 20, 20)
        self._sections_layout.setSpacing(16)
        self._sections_layout.addStretch(1)
        scroll.setWidget(content)

    # -- IPlaceHost (structural, no base class) ----------------------------

    @property
    def surface_id(self) -> str:
        return self._surface.surface_id

    def accepts(self) -> frozenset[Place]:
        return self._surface.accepts

    def place_widget(
        self, place: Place, widget: QWidget, *, title: str | None = None
    ) -> None:
        if place not in self._surface.accepts:
            raise ContributionError(
                f"surface {self.surface_id!r} cannot render {place.value}; "
                f"it accepts {sorted(p.value for p in self._surface.accepts)}."
            )
        if place is not Place.SETTINGS_SECTION:
            raise ContributionError(
                f"surface {self.surface_id!r} accepts {place.value} but this "
                "host only knows how to render SETTINGS_SECTION."
            )
        section = QGroupBox(title or "")
        section_layout = QVBoxLayout(section)
        section_layout.addWidget(widget)
        # Inserted before the trailing stretch, so sections stack from the
        # top and the empty space (if any) always ends up at the bottom.
        self._sections_layout.insertWidget(self._sections_layout.count() - 1, section)
