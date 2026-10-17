import argparse
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import (
    build_handler_parser,
    build_parser,
)
from sagittarius_engine.interfaces.i_config import IConfig


def test_build_parser_headless():
    config = Mock(spec=IConfig)
    config.get.return_value = {
        "sync": {
            "help": "Sync cmd",
            "args": [{"name": "--symbols", "type": "str", "required": True}],
        },
        "stream": {
            "help": "Stream cmd",
            "subparsers": {
                "dest": "action",
                "commands": {
                    "start": {
                        "help": "Start stream",
                        "args": [{"name": "--symbols", "type": "str"}],
                    }
                },
            },
        },
    }

    parser = build_parser(config)

    # Test sync
    args = parser.parse_args(["sync", "--symbols", "BTC"])
    assert args.command == "sync"
    assert args.symbols == "BTC"

    # Test stream start
    args2 = parser.parse_args(["stream", "start", "--symbols", "ETH"])
    assert args2.command == "stream"
    assert args2.action == "start"
    assert args2.symbols == "ETH"


def test_build_handler_parser():
    config = Mock(spec=IConfig)
    config.get.return_value = {
        "sync": {
            "help": "Sync cmd",
            "args": [
                {"name": "--symbols", "type": "str", "required": True},
                {"name": "--days", "type": "int", "default": 30},
            ],
        }
    }

    parser = build_handler_parser(config, "sync")
    args = parser.parse_args(["--symbols", "BTC", "--days", "5"])
    assert args.symbols == "BTC"
    assert args.days == 5

    # Missing required argument
    try:
        parser.parse_args(["--days", "5"])
    except argparse.ArgumentError:
        pass  # Expected since exit_on_error=False
    except SystemExit:
        pass


def test_a_repeatable_argument_with_a_metavar_collects_every_occurrence():
    """`bot edit --set KEY=VALUE --set ...` (`EPIC-038L`): `action` and `metavar` are passed on."""
    config = Mock(spec=IConfig)
    config.get.return_value = {
        "edit": {
            "help": "Edit",
            "args": [
                {
                    "name": "--set",
                    "action": "append",
                    "metavar": "KEY=VALUE",
                    "help": "A setting",
                }
            ],
        }
    }

    parser = build_parser(config)
    args = parser.parse_args(["edit", "--set", "a=1", "--set", "b=2"])

    assert args.set == ["a=1", "b=2"]


def test_the_metavar_is_what_the_help_shows(capsys):
    config = Mock(spec=IConfig)
    config.get.return_value = {
        "edit": {
            "help": "Edit",
            "args": [{"name": "--set", "action": "append", "metavar": "KEY=VALUE"}],
        }
    }

    with pytest.raises(SystemExit):
        build_parser(config).parse_args(["edit", "--help"])

    assert "--set KEY=VALUE" in capsys.readouterr().out
