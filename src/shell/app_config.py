"""Configuration, loaded once, the same way for every entry point (SDD boot 1).

Until now the GUI built its `ConfigManager` in `app_bootstrapper.build()` and the
headless path built a *different* one in `main._load_configuration()`. The two
had drifted: only the GUI parsed `--dev` / `--debug`, so `python -m ...main --dev
sync` set the flag on nothing, and only the headless one loaded
`cli_commands.json`. This is the one loader, and unifying them is the declared
behaviour change of Phase 0: **`--dev` starts working for the headless path**,
and the CLI command table is available to the GUI (harmless, and one fewer way
for the two paths to differ).

The file set, in precedence order (later wins, which is `ConfigManager`'s rule):

| File | Writable | Why |
| :--- | :-: | :--- |
| `app_config.json` | no | shipped defaults |
| `user_config.json` | **yes** | what the user changes; the only file `save()` may touch |
| `cli_commands.json` | no | the CLI's command table; optional, absent in some checkouts |

`ui_state.json` is deliberately **not** here. It is a different `ConfigManager`
with its own writable path (`ConfigManagerStateStore`), because
`ConfigManager.save()` writes exactly one file and window geometry must not
share a file with user settings — nor a save cycle.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from Sagittarius_Elite_Warrior.src.shell.dev_mode import DevMode, resolve_dev_mode
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

#: `src/config/`, from this file's location: `src/shell/app_config.py`.
_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
#: `logs/`, beside the repository root.
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"

APP_CONFIG_FILE = _CONFIG_DIR / "app_config.json"
USER_CONFIG_FILE = _CONFIG_DIR / "user_config.json"
CLI_COMMANDS_FILE = _CONFIG_DIR / "cli_commands.json"


def load_app_config(argv: Sequence[str]) -> tuple[ConfigManager, DevMode]:
    """The application's configuration and what this run decided about
    developer mode. `argv` is the real command line, so `--dev` and `--debug`
    win over the file for both the GUI and the headless path."""
    config_manager = ConfigManager()
    config_manager.load_json(str(APP_CONFIG_FILE))
    config_manager.load_json(str(USER_CONFIG_FILE), writable=True)
    with suppress(FileNotFoundError):
        config_manager.load_json(str(CLI_COMMANDS_FILE))

    dev_mode = resolve_dev_mode(config_manager, argv, str(_LOG_DIR))
    overrides = dev_mode.config_overrides()
    if overrides:
        config_manager.load_dict(overrides)
    return config_manager, dev_mode


def dev_mode_banner(dev_mode: DevMode) -> str | None:
    """The line a developer needs on stdout when a flag turned the mode on:
    where the full session log is, so it can be attached to a bug report.
    `None` when no flag was given — a normal run says nothing."""
    verbosity = dev_mode.verbosity
    if verbosity is None:
        return None
    label = "Debug" if verbosity.is_debug else "Dev"
    return (
        f"{label} mode enabled — log level {verbosity.log_level}, full session "
        f"written to {verbosity.log_file} (attach this file to bug reports)."
    )
