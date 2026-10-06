"""The application's name and the text Help → About shows.

@details Kept apart from `main_window.py` so the window holds composition and
lifecycle only; both are pure strings any part of the shell may read.
"""

from __future__ import annotations

APPLICATION_NAME = "Sagittarius Elite Warrior"


def about_text(venue_text: str, version_text: str) -> str:
    """Help → About: the name, the version and the venue."""
    lines = [APPLICATION_NAME, "A desktop workbench for Binance trading bots."]
    if version_text:
        lines.append(version_text)
    if venue_text:
        lines.append(f"Venue: {venue_text}")
    return "\n".join(lines)
