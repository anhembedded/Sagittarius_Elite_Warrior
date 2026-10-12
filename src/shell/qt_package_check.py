"""The GUI's package pre-flight: PySide6 and pyqtgraph are installed.

`EPIC-038A`: the shared composition checks only what every entry point needs
(`sqlalchemy`); a process with no window must boot on a machine that has no Qt.
The Qt packages are checked here, for the GUI entry point, by the Engine's own
`DependencyValidatorExtension`, wrapped rather than subclassed: the Engine keys
an extension by its class name, and a second `DependencyValidatorExtension`
instance would share the shared check's name (and a subclass would be counted
as another "presence check" by anything that looks for that class).
"""

from __future__ import annotations

from typing import ClassVar

from Sagittarius_Elite_Warrior.src.core.contracts.boot_priority import (
    PREFLIGHT_BOOT_PRIORITY,
)
from sagittarius_engine.extensions.dependency_validator import (
    DependencyValidatorExtension,
)
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.interfaces.i_extension import IExtension

QT_PACKAGES: tuple[str, ...] = ("PySide6", "pyqtgraph")


class QtPackageCheckExtension(IExtension[IEngineContext]):
    """Fails the GUI's boot, naming the packages, when a Qt package is missing."""

    priority: ClassVar[int] = PREFLIGHT_BOOT_PRIORITY

    def __init__(self) -> None:
        self._presence = DependencyValidatorExtension(list(QT_PACKAGES))

    @property
    def required_packages(self) -> list[str]:
        return list(self._presence.required_packages)

    def register(self, context: IEngineContext) -> None:
        self._presence.register(context)

    def boot(self, context: IEngineContext) -> None:
        self._presence.boot(context)

    def shutdown(self, context: IEngineContext) -> None:
        self._presence.shutdown(context)
