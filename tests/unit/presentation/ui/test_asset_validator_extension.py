from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.assets.asset_validator_extension import (
    _DEFAULT_ICONS_DIR,
    REQUIRED_UI_ICONS,
    AssetValidatorExtension,
)


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.logger = MagicMock()
    context.container = MagicMock()
    mock_config = MagicMock()
    mock_config.get.return_value = False
    context.container.resolve.return_value = mock_config
    return context


def test_all_declared_required_ui_icons_exist_on_disk():
    """Guard test: every declared icon in REQUIRED_UI_ICONS must exist in the real assets directory."""
    icons_dir = _DEFAULT_ICONS_DIR
    assert icons_dir.is_dir()
    for icon_name in REQUIRED_UI_ICONS:
        svg_file = icons_dir / f"{icon_name}.svg"
        assert svg_file.is_file(), (
            f"Missing required SVG icon: {icon_name} at {svg_file}"
        )


def test_preflight_passes_cleanly_when_all_assets_exist(mock_context):
    """When all assets are present, preflight passes and logs info."""
    extension = AssetValidatorExtension()
    extension.boot(mock_context)

    mock_context.logger.info.assert_called_once()
    assert "Pre-flight asset check passed" in mock_context.logger.info.call_args[0][0]
    mock_context.logger.error.assert_not_called()
    mock_context.logger.warning.assert_not_called()


def test_preflight_fails_fast_in_dev_mode_when_asset_is_missing(mock_context, tmp_path):
    """In Dev mode (dev.mode=True), missing assets trigger CRITICAL FAULT and sys.exit(1)."""
    # Configure dev mode
    mock_config = MagicMock()
    mock_config.get.side_effect = lambda k, default=None: (
        True if k == "dev.mode" else default
    )
    mock_context.container.resolve.return_value = mock_config

    # Use empty temp directory
    extension = AssetValidatorExtension(
        required_icons=["missing-icon-1", "missing-icon-2"],
        icons_dir=tmp_path,
    )

    with pytest.raises(SystemExit) as exc_info:
        extension.boot(mock_context)

    assert exc_info.value.code == 1
    mock_context.logger.error.assert_called_once()
    err_msg = mock_context.logger.error.call_args[0][0]
    assert "CRITICAL FAULT: Missing required UI icon assets" in err_msg
    assert "missing-icon-1" in err_msg
    assert "missing-icon-2" in err_msg


def test_preflight_warns_and_continues_in_production_mode_when_asset_is_missing(
    mock_context, tmp_path
):
    """In Production mode (dev.mode=False), missing assets log a warning without sys.exit."""
    # Configure production mode (default)
    mock_config = MagicMock()
    mock_config.get.return_value = False
    mock_context.container.resolve.return_value = mock_config

    extension = AssetValidatorExtension(
        required_icons=["missing-icon-prod"],
        icons_dir=tmp_path,
    )

    # Must NOT raise SystemExit
    extension.boot(mock_context)

    mock_context.logger.warning.assert_called_once()
    warning_msg = mock_context.logger.warning.call_args[0][0]
    assert "WARNING: Missing UI icon assets in production" in warning_msg
    assert "missing-icon-prod" in warning_msg
    mock_context.logger.error.assert_not_called()


def test_preflight_custom_subset_passes(tmp_path, mock_context):
    """Custom subset of icons in a custom directory resolves correctly."""
    (tmp_path / "custom1.svg").write_text("<svg></svg>", encoding="utf-8")
    (tmp_path / "custom2.svg").write_text("<svg></svg>", encoding="utf-8")

    extension = AssetValidatorExtension(
        required_icons=["custom1", "custom2"],
        icons_dir=tmp_path,
    )
    extension.boot(mock_context)

    mock_context.logger.info.assert_called_once()
    assert "Pre-flight asset check passed" in mock_context.logger.info.call_args[0][0]
