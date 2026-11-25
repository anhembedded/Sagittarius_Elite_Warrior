"""`EPIC-047F` (condition 4) - the secret filter drops a whole line on a key shape, and each shape is proved alone.

Mutation check: every shape has a sample that **only that shape** catches, so removing one shape turns its test red.
"""

from __future__ import annotations

import time

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.application import (
    bot_log_secret_filter,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.bot_log_secret_filter import (
    SECRET_SHAPES,
    may_carry_a_secret,
    shapes_matching,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    MAX_MESSAGE_CHARS,
)

#: A 64-character run, the shape of an exchange key; not a real one.
_RUN = "Ab12" * 16

_ONLY_BY: dict[str, str] = {
    "assignment": "the exchange said api_key=short rejected",
    "bearer": "sent with Bearer abc.def-ghi for it",
    "webhook-url": "posted to https://hooks.slack.com/x ok",
    "long-token": f"order {_RUN} was placed",
    "pem": "-----BEGIN something",
}


def test_every_shape_has_a_sample_that_only_it_catches() -> None:
    assert sorted(_ONLY_BY) == sorted(name for name, _ in SECRET_SHAPES)
    for name, sample in _ONLY_BY.items():
        assert shapes_matching(sample) == (name,), name


@pytest.mark.parametrize("name", sorted(_ONLY_BY), ids=str)
def test_removing_a_shape_lets_its_own_sample_through(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    kept = tuple(item for item in SECRET_SHAPES if item[0] != name)
    monkeypatch.setattr(bot_log_secret_filter, "SECRET_SHAPES", kept)

    assert may_carry_a_secret(_ONLY_BY[name]) is False


@pytest.mark.parametrize(
    "text",
    [
        "the secret: abc",
        "Signature=deadbeef",
        "listenKey: x",
        "listen key = x",
        "Authorization: Basic zzz",
        "X-MBX-APIKEY: k",
        "password=hunter2",
        "https://discord.com/api/webhooks/1/xyz",
        "https://api.telegram.org/bot123:ABC/send",
        _RUN,
    ],
    ids=lambda text: text[:18],
)
def test_the_named_secrets_are_all_caught(text: str) -> None:
    assert may_carry_a_secret(f"fill {text} done")


@pytest.mark.parametrize(
    "text",
    [
        "fill of 0.5 BTCUSDT at 61234.5 [exit-closed]",
        "price 61000 is above the range 59000-60000 [range-exit]",
        "order SEW-ab12cd-0123456789 placed",
        "the exchange rejects the API key; halting [key-rejected]",
        "position 0.5 differs from the bot's 0.4 (long); halting [position-divergence]",
    ],
    ids=lambda text: text[:18],
)
def test_the_lines_a_bot_really_writes_pass(text: str) -> None:
    assert not may_carry_a_secret(text)


def test_no_shape_is_slow_on_the_longest_text_the_handler_will_scan() -> None:
    for pattern in (
        "http://",
        "https://x/",
        "bearer ",
        "api_key ",
        "-----",
        "a" * 31 + " ",
    ):
        text = (pattern * (MAX_MESSAGE_CHARS // len(pattern) + 1))[:MAX_MESSAGE_CHARS]
        started = time.perf_counter()
        may_carry_a_secret(text)
        assert time.perf_counter() - started < 2.0, pattern
