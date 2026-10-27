"""`EPIC-047D` - the connection profiles are remembered through ui_state, hold no secret, and drop what they cannot read."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    KeySource,
    LinkProfile,
    ReconnectPolicy,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profiles import (
    LinkProfiles,
)

HOME = LinkProfile(name="home vps", host="vps.example", port=2222)
KEYED = replace(
    HOME,
    name="work",
    key_source=KeySource.KEY_FILE,
    key_file="C:\\Users\\me\\.ssh\\id_ed25519",
    known_hosts="C:\\pins\\known_hosts",
    reconnect=ReconnectPolicy(
        first_delay_s=0.5, max_delay_s=20.0, factor=3.0, max_attempts=5
    ),
)


def _remembered(profiles: LinkProfiles) -> LinkProfiles:
    """What a restart does: the captured state, through JSON, into a new object."""
    state = json.loads(json.dumps(profiles.capture_state()))
    fresh = LinkProfiles()
    fresh.restore_state(state)
    return fresh


def test_profiles_and_the_selected_one_survive_a_restart_equal() -> None:
    profiles = LinkProfiles()
    profiles.replace((HOME, KEYED), "work")

    again = _remembered(profiles)

    assert again.profiles == (HOME, KEYED)
    assert again.selected() == KEYED


def test_nothing_remembered_is_no_profile_and_none_selected() -> None:
    profiles = LinkProfiles()
    profiles.restore_state({})

    assert profiles.profiles == () and profiles.selected() is None


def test_what_is_written_to_disk_has_no_secret_field_and_no_key_material() -> None:
    profiles = LinkProfiles()
    profiles.replace((HOME, KEYED), "work")

    text = json.dumps(profiles.capture_state()).lower()

    assert "password" not in text and "passphrase" not in text
    assert "private key" not in text and "begin" not in text


def test_an_entry_with_a_password_field_is_dropped_whole_and_never_written_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    profiles = LinkProfiles()
    profiles.replace((HOME,), None)
    state = json.loads(json.dumps(profiles.capture_state()))
    state["profiles"][0]["password"] = "hunter2"  # noqa: S105 - the secret an old or hostile state file might hold
    fresh = LinkProfiles()

    with caplog.at_level("WARNING", logger="App.LinkProfiles"):
        fresh.restore_state(state)

    assert fresh.profiles == ()
    assert "hunter2" not in json.dumps(fresh.capture_state())
    assert any("home vps" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    "damage",
    [
        lambda p: p.update(port="22"),
        lambda p: p.update(port=0),
        lambda p: p.update(protocol="telnet"),
        lambda p: p.update(key_source="password"),
        lambda p: p.update(key_file="-----BEGIN OPENSSH PRIVATE KEY-----"),
        lambda p: p["reconnect"].update(factor="2"),
        lambda p: p.pop("host"),
    ],
    ids=[
        "port-text",
        "port-zero",
        "protocol",
        "key-source",
        "key-material",
        "factor",
        "no-host",
    ],
)
def test_an_entry_this_build_cannot_read_is_dropped_and_the_rest_kept(damage) -> None:
    profiles = LinkProfiles()
    profiles.replace((HOME, KEYED), "work")
    state = json.loads(json.dumps(profiles.capture_state()))
    damage(state["profiles"][0])
    fresh = LinkProfiles()

    fresh.restore_state(state)

    assert fresh.profiles == (KEYED,)
    assert fresh.selected() == KEYED


def test_a_remembered_selection_that_names_no_profile_is_none() -> None:
    fresh = LinkProfiles()
    fresh.restore_state({"profiles": [], "selected": "gone"})

    assert fresh.selected_name is None


def test_replace_refuses_an_unusable_profile_a_repeated_name_and_a_stranger_selection() -> (
    None
):
    profiles = LinkProfiles()

    with pytest.raises(ValueError, match="host"):
        profiles.replace((replace(HOME, host=""),), None)
    with pytest.raises(ValueError, match="same name"):
        profiles.replace((HOME, HOME), None)
    with pytest.raises(ValueError, match="selected"):
        profiles.replace((HOME,), "nope")
    assert profiles.profiles == ()


def test_a_change_tells_the_listeners_and_the_state_owner_once_and_no_change_tells_nobody() -> (
    None
):
    told: list[str] = []
    profiles = LinkProfiles(on_changed=lambda: told.append("dirty"))
    profiles.subscribe(lambda: told.append("heard"))

    assert profiles.replace((HOME,), "home vps")
    assert not profiles.replace((HOME,), "home vps")

    assert told == ["heard", "dirty"]


def test_a_restore_announces_nothing() -> None:
    told: list[str] = []
    profiles = LinkProfiles(on_changed=lambda: told.append("dirty"))
    profiles.subscribe(lambda: told.append("heard"))

    profiles.restore_state({"profiles": [], "selected": None})

    assert told == []
