"""`EPIC-016` — Screen Registry Pattern: `MainWindow` decoupled from every
concrete screen. See `Docs/SCREEN-REGISTRY-PATTERN/README.md` for the design
and this package's `DECISION_*.md` ADR for what was ratified."""

from .models import NavLocation, NavMetadata, ScreenDescriptor, SectionDescriptor
from .navigation_service import NavigationService
from .ports import INavigationService, IScreenRegistry
from .screen_registry import ScreenRegistry

__all__ = [
    "INavigationService",
    "IScreenRegistry",
    "NavLocation",
    "NavMetadata",
    "NavigationService",
    "ScreenDescriptor",
    "ScreenRegistry",
    "SectionDescriptor",
]
