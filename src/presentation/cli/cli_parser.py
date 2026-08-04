import argparse
from typing import Any, Dict
from sagittarius_engine.interfaces.i_config import IConfig


TYPE_MAPPING = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool
}

def _add_arguments_to_parser(parser: argparse.ArgumentParser, args_list: list[Dict[str, Any]]) -> None:
    for arg in args_list:
        kwargs = {}
        
        if "type" in arg:
            kwargs["type"] = TYPE_MAPPING.get(arg["type"], str)
        if "required" in arg:
            kwargs["required"] = arg["required"]
        if "default" in arg:
            kwargs["default"] = arg["default"]
        if "help" in arg:
            kwargs["help"] = arg["help"]
        if "choices" in arg:
            kwargs["choices"] = arg["choices"]
            
        parser.add_argument(arg["name"], **kwargs)


def _build_command_parser(parser_or_subparser: Any, cmd_name: str, cmd_config: Dict[str, Any]) -> argparse.ArgumentParser:
    if isinstance(parser_or_subparser, argparse._SubParsersAction):
        cmd_parser = parser_or_subparser.add_parser(cmd_name, help=cmd_config.get("help", ""))
    else:
        cmd_parser = parser_or_subparser

    if "args" in cmd_config:
        _add_arguments_to_parser(cmd_parser, cmd_config["args"])
        
    if "subparsers" in cmd_config:
        sub_config = cmd_config["subparsers"]
        subparsers = cmd_parser.add_subparsers(dest=sub_config.get("dest", "subcommand"), required=sub_config.get("required", False))
        for sub_name, sub_cmd_config in sub_config.get("commands", {}).items():
            _build_command_parser(subparsers, sub_name, sub_cmd_config)
            
    return cmd_parser


def build_parser(config: IConfig) -> argparse.ArgumentParser:
    """Builds the main parser (used by headless mode) by reading config."""
    parser = argparse.ArgumentParser(description="Binance Trading Bot CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    cli_commands = config.get("CLI_COMMANDS", {})
    for cmd_name, cmd_config in cli_commands.items():
        _build_command_parser(subparsers, cmd_name, cmd_config)
        
    return parser


def build_handler_parser(config: IConfig, command_name: str) -> argparse.ArgumentParser:
    """Builds an isolated parser for a specific command (used by interactive handlers)."""
    parser = argparse.ArgumentParser(prog=command_name, exit_on_error=False)
    
    cli_commands = config.get("CLI_COMMANDS", {})
    if command_name in cli_commands:
        cmd_config = cli_commands[command_name]
        parser.description = cmd_config.get("help", "")
        # Build args and subparsers directly onto the root parser
        _build_command_parser(parser, command_name, cmd_config)
        
    return parser
