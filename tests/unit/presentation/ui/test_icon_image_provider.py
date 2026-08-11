"""
Tests for IconImageProvider (BOT-030 Phase 1) — the adapter that lets QML
consume the same recolored Lucide icons the QtWidgets UI uses via
`image://icons/<name>/<color>`.

Promoted to sagittarius_engine (BOT-032-ish "second QML consumer" work):
the provider is now generic, taking this app's own IconLoader and icon
color palette as constructor args instead of importing them directly —
these tests construct it the same way app_bootstrapper.py does.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette, get_icon_loader
from PySide6.QtCore import QSize
from sagittarius_engine.extensions.pyside_mvc import IconImageProvider

_ICON_PALETTE = Palette.as_icon_dict()


@pytest.fixture
def provider(qapp):
    return IconImageProvider(get_icon_loader(), _ICON_PALETTE)


@pytest.mark.parametrize(
    "token, expected",
    [
        ("accent", Palette.ACCENT),
        ("success", Palette.SUCCESS),
        ("danger", Palette.DANGER),
        ("muted", Palette.MUTED),
        ("ACCENT", Palette.ACCENT),  # case-insensitive
        ("F3BA2F", "#F3BA2F"),  # raw hex (QML URLs can't carry '#')
    ],
)
def test_resolve_color_accepts_palette_keys_and_raw_hex(provider, token, expected):
    assert provider._resolve_color(token) == expected


@pytest.mark.parametrize("token", ["", "not_a_color", "ZZZZZZ", "12345"])
def test_resolve_color_falls_back_to_muted_for_bad_input(provider, token):
    """Mirrors IconLoader's never-raise contract: a malformed icon URL must
    degrade to a default color, not take down the screen rendering it."""
    assert provider._resolve_color(token) == Palette.MUTED


def test_parse_id_splits_name_and_color(provider):
    assert provider._parse_id("play/success") == ("play", Palette.SUCCESS)


def test_parse_id_without_color_uses_muted_default(provider):
    assert provider._parse_id("play") == ("play", Palette.MUTED)


def test_request_pixmap_returns_icon_at_requested_size(provider):
    size = QSize()
    pixmap = provider.requestPixmap("play/success", size, QSize(32, 32))

    assert not pixmap.isNull()
    assert pixmap.size() == QSize(32, 32)
    # Qt reads the produced size back out of this out-parameter.
    assert size == QSize(32, 32)


def test_request_pixmap_uses_default_size_when_unconstrained(provider):
    """QML omits sourceSize often; an invalid requested size must still
    produce a usable icon rather than a 0x0 pixmap."""
    size = QSize()
    pixmap = provider.requestPixmap("play", size, QSize(-1, -1))

    assert not pixmap.isNull()
    assert pixmap.width() > 0


def test_request_pixmap_for_unknown_icon_returns_blank_not_error(provider):
    """Delegates to IconLoader's blank-icon fallback — a typo'd icon name in
    QML shows nothing rather than raising into the render loop."""
    size = QSize()
    pixmap = provider.requestPixmap("no_such_icon/accent", size, QSize(20, 20))

    assert not pixmap.isNull()
    assert pixmap.size() == QSize(20, 20)
