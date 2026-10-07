"""`EnvironmentBanner` — the global "which funds am I trading" banner every
mode shows in the workbench host's top row (`EPIC-021K`); a calm content
(`BannerSeverity.INFO`) takes no strip (`environment_banner_factory`,
`BUG-156`).

@details Content is computed once, at boot, from the venues the build assembles —
it never changes within a session (see this package's own
`environment_banner_content.py` docstring). `EnvironmentBannerContent` is the
"ViewModel" in the plainer MVVM sense: a pure, immutable projection of those venues
into what the View renders, computed by `venue_banner_content()` and handed to
`EnvironmentBanner` at construction.
"""

from __future__ import annotations

from .environment_banner import EnvironmentBanner
from .environment_banner_content import (
    BannerSeverity,
    EnvironmentBannerContent,
    venue_banner_content,
)
from .environment_banner_factory import environment_banner_factory

__all__ = [
    "BannerSeverity",
    "EnvironmentBanner",
    "EnvironmentBannerContent",
    "environment_banner_factory",
    "venue_banner_content",
]
