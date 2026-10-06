"""Which runs get a banner strip at all (`BUG-156`)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from .environment_banner import EnvironmentBanner
from .environment_banner_content import BannerSeverity, EnvironmentBannerContent


def environment_banner_factory(
    content: EnvironmentBannerContent,
) -> Callable[[], QWidget | None]:
    """@brief The factory `WorkbenchSurface.set_environment_banner_factory`
    takes: a banner per surface, except where `content` is calm.

    @details A strip across every mode is the loudest thing in the window, so
    it is kept for what must interrupt: testnet funds and the venue
    mismatches that make a price on screen differ from the fill. "Trading is
    OFF. Data view only." is the resting state, and it is already said
    persistently where a desktop app keeps its mode: the window title and the
    status bar's venue label (`MainWindow._show_venue`). Neither warning kind
    can be switched off by the user (`WorkbenchSurface._add_environment_banner`).
    """
    if content.severity is BannerSeverity.INFO:
        return lambda: None
    return lambda: EnvironmentBanner(content)
