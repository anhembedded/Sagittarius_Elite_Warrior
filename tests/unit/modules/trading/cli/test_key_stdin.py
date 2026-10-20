"""`BOT-200` — `key check` takes a key from standard input and from nowhere else."""

from __future__ import annotations

import io

from Sagittarius_Elite_Warrior.src.modules.trading.cli.key_stdin import read_key_from


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_a_pipe_gives_the_key_on_the_first_line_and_the_secret_on_the_second() -> None:
    credentials = read_key_from(io.StringIO("the-key\nthe-secret\n"))

    assert (credentials.api_key, credentials.api_secret) == ("the-key", "the-secret")


def test_only_the_line_ending_is_dropped_so_a_stray_space_is_the_checks_to_refuse() -> (
    None
):
    credentials = read_key_from(io.StringIO("the-key \r\n the-secret\r\n"))

    assert (credentials.api_key, credentials.api_secret) == ("the-key ", " the-secret")


def test_a_missing_line_is_an_empty_value_never_an_error_or_a_guess() -> None:
    assert read_key_from(io.StringIO("")).api_key == ""
    only_key = read_key_from(io.StringIO("the-key"))
    assert (only_key.api_key, only_key.api_secret) == ("the-key", "")


def test_a_terminal_is_asked_for_each_value_with_the_echo_off_and_stdin_is_not_read() -> (
    None
):
    prompts: list[str] = []
    answers = iter(["typed-key", "typed-secret"])

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    terminal = _Terminal("this must never be read\n")

    credentials = read_key_from(terminal, ask)

    assert (credentials.api_key, credentials.api_secret) == (
        "typed-key",
        "typed-secret",
    )
    assert prompts == ["API key: ", "API secret: "]
    assert terminal.tell() == 0
