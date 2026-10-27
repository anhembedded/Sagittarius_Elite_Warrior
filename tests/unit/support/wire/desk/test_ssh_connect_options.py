"""`EPIC-047D` - the two traps of `asyncssh.connect` are closed in the function that builds its arguments.

`client_keys=None` turns key login off and `known_hosts=None` turns host-key verification off
(DERISK §3.3, SSH record D4). A profile never reaches either.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    KeySource,
    LinkProfile,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.ssh_connect_options import (
    connect_options,
    known_hosts_path,
)

AGENT = LinkProfile(name="vps", host="vps.example", port=2222)
KEY = replace(AGENT, key_source=KeySource.KEY_FILE, key_file="~/keys/id_ed25519")


def test_a_profile_with_no_key_file_leaves_client_keys_out_and_never_passes_none() -> (
    None
):
    options = connect_options(AGENT)

    assert "client_keys" not in options
    assert options.get("client_keys", "absent") is not None


@pytest.mark.parametrize("profile", [AGENT, KEY])
def test_no_profile_ever_passes_none_for_client_keys_or_known_hosts(
    profile: LinkProfile,
) -> None:
    options = connect_options(profile)

    assert options.get("client_keys", []) is not None
    assert options["known_hosts"] is not None


def test_a_key_file_profile_names_exactly_that_key_and_leaves_the_agent_out() -> None:
    options = connect_options(KEY)

    assert options["client_keys"] == [str(Path("~/keys/id_ed25519").expanduser())]
    assert options["agent_path"] is None


def test_the_host_key_is_pinned_to_the_users_known_hosts_unless_the_profile_names_another() -> (
    None
):
    assert connect_options(AGENT)["known_hosts"] == str(
        Path("~/.ssh/known_hosts").expanduser()
    )
    assert known_hosts_path(replace(AGENT, known_hosts="/etc/pins")) == Path(
        "/etc/pins"
    )


def test_the_arguments_carry_the_endpoint_the_account_and_the_timeout() -> None:
    options = connect_options(AGENT)

    assert (options["host"], options["port"], options["username"]) == (
        "vps.example",
        2222,
        "sew",
    )
    assert options["connect_timeout"] == AGENT.connect_timeout_s


def test_nothing_in_the_arguments_can_be_a_password_or_a_prompt() -> None:
    options = connect_options(KEY)

    assert "password" not in options and "passphrase" not in options
    assert options["preferred_auth"] == "publickey"
    assert options["config"] == []
