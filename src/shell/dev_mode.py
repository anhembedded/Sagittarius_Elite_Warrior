"""Developer mode: read once, at boot, for the whole run (SDD-05, ADR D14).

Three facts make this a value and not a lookup:

1. **It gates a surface.** `dev_board` exists or does not exist for a run; a
   value that could change mid-run would mean loading and unloading a module,
   which the mechanism deliberately cannot do.
2. **The command line wins.** `--dev` / `--debug` on `sys.argv` turn it on even
   when the file says false, because that is what a developer typing the flag
   means. The Engine's `resolve_dev_verbosity()` already parses the pair and
   also decides the log level and file, so it stays the one parser.
3. **The switch takes effect on restart.** The Welcome screen writes `dev.mode`
   through `IConfigWriter` and offers a restart; nothing re-reads it in place.

Both entry points call `resolve_dev_mode()` — that is the declared behaviour
change of Phase 0: `--dev` starts working for the headless path too, because it
used to be parsed only by the GUI bootstrapper.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from sagittarius_engine.infrastructure.logging.dev_verbosity import (
    DevVerbosity,
    resolve_dev_verbosity,
)
from sagittarius_engine.interfaces.i_config import IConfig


@dataclass(frozen=True, slots=True)
class DevMode:
    """What this run decided about developer mode, and why."""

    is_enabled: bool
    #: Set when a command-line flag decided it; `None` when the file did.
    verbosity: DevVerbosity | None = None

    @property
    def came_from_the_command_line(self) -> bool:
        return self.verbosity is not None

    def config_overrides(self) -> dict[str, object]:
        """What the flag adds to configuration, so the whole app sees one value.
        Empty when no flag was given — the file's value already stands."""
        if self.verbosity is None:
            return {}
        return {
            ConfigKeys.DEV_MODE.value: True,
            "log.level": self.verbosity.log_level,
            "log.file": self.verbosity.log_file,
        }


def resolve_dev_mode(config: IConfig, argv: Sequence[str], log_dir: str) -> DevMode:
    """`--dev` / `--debug` first, then the configuration file."""
    verbosity = resolve_dev_verbosity(argv, log_dir)
    if verbosity is not None:
        return DevMode(is_enabled=True, verbosity=verbosity)
    return DevMode(is_enabled=bool(config.get(ConfigKeys.DEV_MODE.value, False)))
