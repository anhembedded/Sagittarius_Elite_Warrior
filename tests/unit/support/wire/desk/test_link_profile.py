"""`EPIC-047D` - a profile names where a key is and never holds one; its policy backs off and stops."""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    KeySource,
    LinkProfile,
    ReconnectPolicy,
    problem_of,
)

GOOD = LinkProfile(name="vps", host="vps.example")


def test_a_plain_profile_is_usable_and_defaults_to_the_sew_account_and_the_agent() -> (
    None
):
    assert problem_of(GOOD) is None
    assert GOOD.user == "sew"
    assert GOOD.key_source is KeySource.AGENT


@pytest.mark.parametrize(
    "broken",
    [
        replace(GOOD, name=""),
        replace(GOOD, name=" vps"),
        replace(GOOD, name="x" * 41),
        replace(GOOD, host=""),
        replace(GOOD, host="a b"),
        replace(GOOD, port=0),
        replace(GOOD, port=65536),
        replace(GOOD, user=""),
        replace(GOOD, connect_timeout_s=0.0),
        replace(GOOD, connect_timeout_s=float("nan")),
        replace(GOOD, key_source=KeySource.KEY_FILE, key_file=""),
        replace(GOOD, key_file="/home/me/.ssh/id_ed25519"),
        replace(GOOD, reconnect=ReconnectPolicy(max_attempts=0)),
        replace(GOOD, reconnect=ReconnectPolicy(factor=0.5)),
        replace(GOOD, reconnect=ReconnectPolicy(first_delay_s=-1.0)),
    ],
)
def test_a_profile_the_link_cannot_use_says_why(broken: LinkProfile) -> None:
    assert problem_of(broken)


@pytest.mark.parametrize(
    "pasted",
    [
        "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk=\n-----END OPENSSH PRIVATE KEY-----",
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIexample me@desk",
        "C:\\keys\\id\nsecond line",
    ],
)
def test_key_material_in_the_key_file_field_is_refused(pasted: str) -> None:
    profile = replace(GOOD, key_source=KeySource.KEY_FILE, key_file=pasted)

    assert problem_of(profile) is not None
    assert "file" in str(problem_of(profile))


def test_a_path_to_a_key_file_is_accepted() -> None:
    profile = replace(
        GOOD, key_source=KeySource.KEY_FILE, key_file="C:\\Users\\me\\.ssh\\id_ed25519"
    )

    assert problem_of(profile) is None


def test_the_profile_has_no_field_that_could_hold_a_password_or_a_passphrase() -> None:
    names = set(LinkProfile.__dataclass_fields__)

    assert not {n for n in names if "pass" in n or "secret" in n or "private" in n}


def test_the_first_retry_is_at_once_then_waits_grow_to_the_cap() -> None:
    policy = ReconnectPolicy(first_delay_s=0.0, max_delay_s=10.0, factor=2.0)
    delays = policy.delays()

    assert [next(delays) for _ in range(7)] == [0.0, 1.0, 2.0, 4.0, 8.0, 10.0, 10.0]


def test_a_policy_with_a_limit_ends_its_delays_after_that_many_attempts() -> None:
    policy = ReconnectPolicy(first_delay_s=0.0, max_attempts=3)

    assert len(list(policy.delays())) == 3
