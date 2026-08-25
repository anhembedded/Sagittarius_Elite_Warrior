"""
Sanity test for BOT-071: Real composition root & DI verification for AssetValidatorExtension.
Asserts that create_app() wires AssetValidatorExtension into app.modules and boots cleanly.
"""

import os
from unittest.mock import patch

from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.assets.asset_validator_extension import (
    AssetValidatorExtension,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


def test_asset_validator_extension_is_wired_in_real_create_app():
    """Sanity (DI): create_app() must register AssetValidatorExtension in app.modules."""
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )

    app = create_app(config_manager)

    # Assert AssetValidatorExtension is present in modules
    asset_validator_modules = [
        m for m in app.modules if isinstance(m, AssetValidatorExtension)
    ]
    assert len(asset_validator_modules) == 1, (
        "AssetValidatorExtension must be registered in app.modules during create_app()"
    )


def test_asset_validator_boots_cleanly_in_real_app_boot():
    """Sanity (Boot): Booting real app executes AssetValidatorExtension against real disk assets."""
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )

    app = create_app(config_manager)

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        # Boot should succeed with zero missing assets
        app.boot()
        try:
            # Confirm app is booted and lifecycle is running
            assert app.context is not None
        finally:
            app.stop()
