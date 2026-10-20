"""`logs` is a launcher verb with options of its own, not a `cli_commands.json` entry (`BOT-199`)."""

from __future__ import annotations

import argparse

import pytest
from Sagittarius_Elite_Warrior.src.support.cli_host.launcher_verb import (
    LauncherVerb,
    add_launcher_verbs,
)
from Sagittarius_Elite_Warrior.src.support.log_view.log_viewer_cli import (
    configure_logs_parser,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_launcher_verbs(
        parser.add_subparsers(dest="command"),
        (LauncherVerb("logs", "Show a log", configure=configure_logs_parser),),
    )
    return parser


def test_the_verb_accepts_every_documented_flag() -> None:
    args = _parser().parse_args(
        [
            "logs",
            "--file",
            "a.log",
            "--follow",
            "--level",
            "warning",
            "--bot",
            "uie03d",
            "--tag",
            "health",
            "--since",
            "2h",
            "--no-color",
        ]
    )

    assert (args.command, args.follow, args.level, args.bot, args.tag, args.since) == (
        "logs",
        True,
        "warning",
        "uie03d",
        "health",
        "2h",
    )
    assert args.no_color is True


def test_a_flag_the_verb_did_not_declare_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as stop:
        _parser().parse_args(["logs", "--colour-me-bad"])

    assert stop.value.code == 2
