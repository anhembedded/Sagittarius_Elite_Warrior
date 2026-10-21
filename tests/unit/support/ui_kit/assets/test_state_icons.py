"""`EPIC-043C`: the icons a state uses are real Lucide drawings, not blanks."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets.icon_loader import IconLoader

_STATE_ICONS = (
    "play",
    "pause",
    "rotate-ccw",
    "triangle-alert",
    "square",
    "clock",
    "circle-check-big",
    "circle-x",
)


@pytest.mark.parametrize("name", _STATE_ICONS)
def test_a_state_icon_renders_something(qapp, name: str) -> None:
    image = IconLoader().get_icon(name, "black", 24).pixmap(24, 24).toImage()

    assert any(
        image.pixelColor(x, y).alpha() > 0
        for x in range(image.width())
        for y in range(image.height())
    )
