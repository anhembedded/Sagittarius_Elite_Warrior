import argparse
from typing import Any

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.cli_host.launcher_verb import (
    LauncherVerb,
    add_launcher_verbs,
)
from sagittarius_engine.interfaces.i_config import IConfig

#: `--verbose` (`BOT-185`): the log on the console of a command that keeps it in a
#: file. On every command, at any position (`bot list --verbose`, `--verbose bot
#: list`), so it is a parent parser and not an entry of `cli_commands.json`.
#: `SUPPRESS` leaves the attribute off unless given, so a sub-parser's default can
#: never overwrite a flag the parent parser already read.
VERBOSE_DEST = "verbose"
_VERBOSE_PARENT = argparse.ArgumentParser(add_help=False)
_VERBOSE_PARENT.add_argument(
    "--verbose",
    dest=VERBOSE_DEST,
    action="store_true",
    default=argparse.SUPPRESS,
    help="Show the application log on the console. A command that only reads keeps "
    "it in a file under <data root>/logs and shows warnings and errors only",
)

TYPE_MAPPING = {"str": str, "int": int, "float": float, "bool": bool}


def _add_arguments_to_parser(
    parser: argparse.ArgumentParser, args_list: list[dict[str, Any]]
) -> None:
    for arg in args_list:
        kwargs = {}

        if "action" in arg:
            # e.g. "store_true" for a boolean flag (`--json`, EPIC-021E) —
            # mutually exclusive with `type` in argparse itself, so this
            # branch skips the type-mapping below entirely rather than
            # letting a stray "type" key in the JSON produce a TypeError.
            kwargs["action"] = arg["action"]
        elif "type" in arg:
            kwargs["type"] = TYPE_MAPPING.get(arg["type"], str)
        if "required" in arg:
            kwargs["required"] = arg["required"]
        if "default" in arg:
            kwargs["default"] = arg["default"]
        if "help" in arg:
            kwargs["help"] = arg["help"]
        if "choices" in arg:
            kwargs["choices"] = arg["choices"]
        if "metavar" in arg:
            kwargs["metavar"] = arg["metavar"]

        parser.add_argument(arg["name"], **kwargs)


def _build_command_parser(
    parser_or_subparser: argparse.ArgumentParser | argparse._SubParsersAction,
    cmd_name: str,
    cmd_config: dict[str, Any],
) -> argparse.ArgumentParser:
    if isinstance(parser_or_subparser, argparse._SubParsersAction):
        cmd_parser = parser_or_subparser.add_parser(
            cmd_name, help=cmd_config.get("help", ""), parents=[_VERBOSE_PARENT]
        )
    else:
        cmd_parser = parser_or_subparser

    if "args" in cmd_config:
        _add_arguments_to_parser(cmd_parser, cmd_config["args"])

    if "subparsers" in cmd_config:
        sub_config = cmd_config["subparsers"]
        subparsers = cmd_parser.add_subparsers(
            dest=sub_config.get("dest", "subcommand"),
            required=sub_config.get("required", False),
        )
        for sub_name, sub_cmd_config in sub_config.get("commands", {}).items():
            _build_command_parser(subparsers, sub_name, sub_cmd_config)

    return cmd_parser


def build_parser(
    config: IConfig, launcher_verbs: tuple[LauncherVerb, ...] = ()
) -> argparse.ArgumentParser:
    """Builds the main parser (used by headless mode) by reading config.

    `launcher_verbs` (`EPIC-038B`) are the words that start a mode rather than
    run a report command (`gui`, `shell`); they are listed in `--help` beside
    the commands but live in the entry point, not in `cli_commands.json`.
    """
    parser = argparse.ArgumentParser(
        description="Binance Trading Bot CLI", parents=[_VERBOSE_PARENT]
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    add_launcher_verbs(subparsers, launcher_verbs)

    cli_commands = config.get(ConfigKeys.CLI_COMMANDS.value, {})
    for cmd_name, cmd_config in cli_commands.items():
        _build_command_parser(subparsers, cmd_name, cmd_config)

    return parser


def build_handler_parser(config: IConfig, command_name: str) -> argparse.ArgumentParser:
    """Builds an isolated parser for a specific command (used by interactive handlers)."""
    parser = argparse.ArgumentParser(prog=command_name, exit_on_error=False)

    cli_commands = config.get(ConfigKeys.CLI_COMMANDS.value, {})
    if command_name in cli_commands:
        cmd_config = cli_commands[command_name]
        parser.description = cmd_config.get("help", "")
        # Build args and subparsers directly onto the root parser
        _build_command_parser(parser, command_name, cmd_config)

    return parser
