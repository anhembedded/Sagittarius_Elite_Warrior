"""A launcher verb is listed in `--help` and accepts only its declared flags (`EPIC-038B`)."""

from __future__ import annotations

import argparse

import pytest
from Sagittarius_Elite_Warrior.src.support.cli_host.launcher_verb import (
    LauncherVerb,
    add_launcher_verbs,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_launcher_verbs(
        parser.add_subparsers(dest="command"),
        (LauncherVerb("gui", "Open the window", ("--dev",)),),
    )
    return parser


def test_a_verb_is_a_command_with_its_flags() -> None:
    args = _parser().parse_args(["gui", "--dev"])

    assert args.command == "gui"
    assert args.dev is True


def test_a_flag_the_verb_did_not_declare_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as raised:
        _parser().parse_args(["gui", "--bogus"])

    assert raised.value.code == 2


def test_a_verb_appears_in_the_help(capsys: pytest.CaptureFixture[str]) -> None:
    _parser().print_help()

    assert "Open the window" in capsys.readouterr().out
