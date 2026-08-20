"""
Integration test for BOT-071: Multi-component lifecycle integration between App, ConfigManager,
and AssetValidatorExtension.
"""

from unittest.mock import patch

import pytest

from Sagittarius_Elite_Warrior.src.presentation.ui.assets.asset_validator_extension import (
    AssetValidatorExtension,
)
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus


@pytest.fixture
def clean_app_context():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    config_manager = ConfigManager()

    container.singleton(IEventBus, event_bus)
    container.singleton(IConfig, config_manager)

    app = App(container, event_bus)
    yield app, config_manager
    if app.lifecycle.is_booted and not (
        app.lifecycle.is_stopping or app.lifecycle.is_stopped
    ):
        app.stop()


def test_asset_preflight_integration_passes_in_production_mode(clean_app_context):
    """Integration: App boots cleanly with AssetValidatorExtension in production mode."""
    app, config_manager = clean_app_context
    config_manager.set("dev.mode", False)

    app.use(AssetValidatorExtension())
    app.boot()
    assert app.lifecycle.is_booted


def test_asset_preflight_integration_fails_fast_in_dev_mode_with_broken_assets(
    clean_app_context, tmp_path
):
    """Integration: App boot raises SystemExit(1) when an asset is missing in dev mode."""
    app, config_manager = clean_app_context
    config_manager.set("dev.mode", True)

    # Empty tmp_path -> missing required icons
    extension = AssetValidatorExtension(
        required_icons=["non-existent-icon"],
        icons_dir=tmp_path,
    )
    app.use(extension)

    with pytest.raises(SystemExit) as exc_info:
        app.boot()

    assert exc_info.value.code == 1


def test_asset_preflight_integration_warns_and_continues_in_production_with_missing_assets(
    clean_app_context, tmp_path
):
    """Integration: App boot logs warning and finishes boot in production mode with missing assets."""
    app, config_manager = clean_app_context
    config_manager.set("dev.mode", False)

    extension = AssetValidatorExtension(
        required_icons=["non-existent-icon"],
        icons_dir=tmp_path,
    )
    app.use(extension)

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.assets.asset_validator_extension.logger.warning"
    ) as mock_warning:
        app.boot()

        assert app.lifecycle.is_booted
        mock_warning.assert_called_once()
        assert (
            "WARNING: Missing UI icon assets in production"
            in mock_warning.call_args[0][0]
        )
