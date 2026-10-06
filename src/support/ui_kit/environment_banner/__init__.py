"""`EnvironmentBanner` — the global "which venue am I in" banner every
mode shows in the workbench host's top row (`EPIC-021K`), except for the
calm "Trading is OFF" state, which the window title and the status bar say
(`environment_banner_factory`, `BUG-156`).

@details Content is computed once, at boot, from `VenueAlignment` — it
never changes within a session (`EXCHANGE_MARKET_DATA_VENUE`/
`EXCHANGE_TRADING_VENUE` are file-config-only, no Settings UI edits them
live; see this package's own `environment_banner_content.py`
docstring). There is therefore no reactive ViewModel here in the
Signal sense other screens' ViewModels use — `EnvironmentBannerContent`
is the "ViewModel" in the plainer MVVM sense: a pure, immutable projection
of `VenueAlignment` into what the View renders, computed by
`venue_alignment_banner_content()` and handed to `EnvironmentBanner` at
construction.
"""

from __future__ import annotations

from .environment_banner import EnvironmentBanner
from .environment_banner_content import (
    BannerSeverity,
    EnvironmentBannerContent,
    venue_alignment_banner_content,
)
from .environment_banner_factory import environment_banner_factory

__all__ = [
    "BannerSeverity",
    "EnvironmentBanner",
    "EnvironmentBannerContent",
    "environment_banner_factory",
    "venue_alignment_banner_content",
]
