"""The QtWidgets ↔ QML bridge layer — the only place this app touches
`QQuickWidget`. One abstraction per file: `QuickSurface` (the host),
`QuickSizePolicy` (how it sizes). Why it exists: `BUG-115`."""

from .quick_surface import QuickSurface
from .size_policy import QuickSizePolicy

__all__ = ["QuickSizePolicy", "QuickSurface"]
