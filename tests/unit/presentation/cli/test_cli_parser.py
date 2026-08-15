import argparse
from unittest.mock import Mock

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
