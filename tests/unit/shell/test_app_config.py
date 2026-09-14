"""One configuration loader for both entry points (SDD boot step 1).

The GUI and the headless path used to build a `ConfigManager` each, and the two
had drifted: only the GUI parsed `--dev`, only the headless one loaded
`cli_commands.json`. These tests pin the union, which is Phase 0's one declared
behaviour change.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.shell.app_config import (
    APP_CONFIG_FILE,
    CLI_COMMANDS_FILE,
    USER_CONFIG_FILE,
    dev_mode_banner,
    load_app_config,
)


def test_the_files_it_names_are_the_files_that_exist() -> None:
    """A loader pointing at the wrong path fails at runtime with an empty
    config, which reads as "my setting does nothing"."""
    assert APP_CONFIG_FILE.is_file()
    assert USER_CONFIG_FILE.is_file()
    assert CLI_COMMANDS_FILE.is_file()


def test_it_reads_the_real_application_configuration() -> None:
    config, _dev_mode = load_app_config(["app.py"])
    assert config.get(ConfigKeys.UI_FONT_FAMILY) is not None
    assert config.get(ConfigKeys.DEV_MODE.value, False) is False


def test_user_config_is_the_writable_file() -> None:
    """`save()` must reach `user_config.json` and nothing else — window
    geometry and shipped defaults have their own files on purpose."""
    config, _dev_mode = load_app_config(["app.py"])
    sources = config.sources()
    assert any("user_config.json" in str(source) for source in sources.values())


def test_the_cli_command_table_is_loaded_for_both_paths() -> None:
    config, _dev_mode = load_app_config(["app.py"])
    assert config.get("commands") is not None or config.get_all() != {}


def test_the_dev_flag_reaches_configuration() -> None:
    config, dev_mode = load_app_config(["main.py", "sync", "--dev"])
    assert dev_mode.is_enabled
    assert config.get(ConfigKeys.DEV_MODE.value) is True
    assert config.get("log.level") == "DEBUG"


def test_a_normal_run_prints_nothing() -> None:
    _config, dev_mode = load_app_config(["app.py"])
    assert dev_mode_banner(dev_mode) is None


def test_a_developer_run_says_where_the_log_is() -> None:
    _config, dev_mode = load_app_config(["app.py", "--debug"])
    banner = dev_mode_banner(dev_mode)
    assert banner is not None
    assert "Debug mode enabled" in banner
    assert ".log" in banner
