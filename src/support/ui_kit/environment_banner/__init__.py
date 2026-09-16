"""`EnvironmentBanner` — the global "which venue am I in" banner every
screen shows in its `PageShell` header (`EPIC-021K`).

@details Content is computed once, at boot, from `VenueAlignment` — it
never changes within a session (`EXCHANGE_MARKET_DATA_VENUE`/
`EXCHANGE_TRADING_VENUE` are file-config-only, no Settings UI edits them
live; see this package's own `environment_banner_content.py`
docstring). There is therefore no reactive ViewModel here in the
Signal/Property sense other screens' ViewModels use — `EnvironmentBannerContent`
is the "ViewModel" in the plainer MVVM sense: a pure, immutable projection
of `VenueAlignment` into what the View renders, computed by
`venue_alignment_banner_content()` and handed to `EnvironmentBanner` at
construction.
"""

from __future__ import annotations

from .environment_banner import EnvironmentBanner
from .environment_banner_content import (
    EnvironmentBannerContent,
    venue_alignment_banner_content,
)

__all__ = [
    "EnvironmentBanner",
    "EnvironmentBannerContent",
    "venue_alignment_banner_content",
]
