"""`EPIC-016` — Screen Registry Pattern: `MainWindow` decoupled from every
concrete screen. See `Docs/SCREEN-REGISTRY-PATTERN/README.md` for the design
and this package's `DECISION_*.md` ADR for what was ratified."""

from .abstract_screen_module import AbstractScreenModule
from .models import NavLocation, NavMetadata, ScreenDescriptor, SectionDescriptor
from .ports import IScreenRegistry
from .screen_registry import ScreenRegistry

__all__ = [
    "AbstractScreenModule",
    "IScreenRegistry",
    "NavLocation",
    "NavMetadata",
    "ScreenDescriptor",
    "ScreenRegistry",
    "SectionDescriptor",
]
