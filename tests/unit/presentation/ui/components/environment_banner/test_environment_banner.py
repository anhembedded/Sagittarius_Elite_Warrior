from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.presentation.ui.components.environment_banner import (
    EnvironmentBanner,
    EnvironmentBannerContent,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.surfaces.banner import Severity


def test_renders_the_given_content(qapp) -> None:
    banner = EnvironmentBanner(
        EnvironmentBannerContent(
            icon="⚠", message="Chart MAINNET, lệnh TESTNET.", severity=Severity.DANGER
        )
    )

    assert banner.objectName() == "environmentBanner"
    assert banner.message == "Chart MAINNET, lệnh TESTNET."
    assert banner.icon == "⚠"
    assert banner.severity is Severity.DANGER
