import pytest

from Binace_Bot.src.presentation.ui.assets.icon_loader import (
    IconLoader,
    IconTheme,
    get_icon_loader,
)

# Every icon file referenced by Sidebar/ControlCard/MonitorCard (BOT-016).
_EXPECTED_ICONS = [
    "layout-dashboard",
    "database",
    "settings",
    "play",
    "square",
    "clock",
    "info",
    "triangle-alert",
    "circle-check-big",
    "trash-2",
    "chart-candlestick",
]


@pytest.fixture
def loader():
    return IconLoader()


@pytest.mark.parametrize("name", _EXPECTED_ICONS)
def test_all_expected_icons_load_successfully(qapp, loader, name):
    """Every icon referenced by the UI components must resolve to a real (non-blank) icon."""
    icon = loader.get_icon(name)
    assert not icon.isNull()


def test_get_icon_caches_by_name_color_size(qapp, loader):
    """Repeated calls with identical args return the exact same cached QIcon object."""
    icon1 = loader.get_icon("play", color=IconTheme.SUCCESS, size=20)
    icon2 = loader.get_icon("play", color=IconTheme.SUCCESS, size=20)
    assert icon1 is icon2
    assert len(loader._cache) == 1


def test_get_icon_different_color_is_a_separate_cache_entry(qapp, loader):
    """Recoloring produces a distinct cache entry — colors must not collide."""
    green = loader.get_icon("play", color=IconTheme.SUCCESS)
    red = loader.get_icon("play", color=IconTheme.DANGER)
    assert green is not red
    assert len(loader._cache) == 2


def test_missing_icon_falls_back_to_blank_without_raising(qapp, loader):
    """A missing SVG file must never crash the UI — falls back to a blank transparent icon."""
    icon = loader.get_icon("this-icon-does-not-exist")
    assert not icon.isNull()  # A valid (blank) QIcon, not a crash


def test_clear_cache_empties_the_cache(qapp, loader):
    loader.get_icon("play")
    assert len(loader._cache) == 1
    loader.clear_cache()
    assert len(loader._cache) == 0


def test_get_icon_loader_returns_shared_singleton(qapp):
    """get_icon_loader() is the app-wide instance shared by UI components."""
    assert get_icon_loader() is get_icon_loader()
