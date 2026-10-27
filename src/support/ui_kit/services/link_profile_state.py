"""`EPIC-047D` — a connection profile as remembered state, and back.

The profile goes to `ui_state.json` through the repository's own mechanism (`IStateContributor`,
the way `TickFlashPreference` does), as a flat object of the fields `LinkProfile` has — a reference to
a key file, never a key. Reading is strict: an entry with a field this build does not know (a
`password`, say), a value of the wrong type or a profile `problem_of` refuses is **dropped whole**
with a WARNING naming it, never kept half read and never echoed back to disk.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    KeySource,
    LinkProfile,
    LinkProtocol,
    ReconnectPolicy,
    problem_of,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import JsonValue

logger = logging.getLogger("App.LinkProfiles")

_PROFILE_KEYS = {
    "name",
    "host",
    "port",
    "user",
    "protocol",
    "key_source",
    "key_file",
    "known_hosts",
    "connect_timeout_s",
    "reconnect",
}
_RECONNECT_KEYS = {"first_delay_s", "max_delay_s", "factor", "max_attempts"}


def profile_to_state(profile: LinkProfile) -> dict[str, JsonValue]:
    reconnect = profile.reconnect
    return {
        "name": profile.name,
        "host": profile.host,
        "port": profile.port,
        "user": profile.user,
        "protocol": profile.protocol.value,
        "key_source": profile.key_source.value,
        "key_file": profile.key_file,
        "known_hosts": profile.known_hosts,
        "connect_timeout_s": profile.connect_timeout_s,
        "reconnect": {
            "first_delay_s": reconnect.first_delay_s,
            "max_delay_s": reconnect.max_delay_s,
            "factor": reconnect.factor,
            "max_attempts": reconnect.max_attempts,
        },
    }


def profile_from_state(document: object) -> LinkProfile | None:
    """The profile, or `None` (with a warning) when the entry cannot be read."""
    try:
        profile = _decode(document)
    except (ValueError, TypeError) as failure:
        label = document.get("name") if isinstance(document, Mapping) else None
        logger.warning(
            "[link-profiles] a remembered profile %r was dropped: %s", label, failure
        )
        return None
    problem = problem_of(profile)
    if problem is not None:
        logger.warning(
            "[link-profiles] the remembered profile %r was dropped: %s",
            profile.name,
            problem,
        )
        return None
    return profile


def _decode(document: object) -> LinkProfile:
    if not isinstance(document, Mapping) or document.keys() != _PROFILE_KEYS:
        raise ValueError("it does not have exactly the fields of a profile")
    reconnect = document["reconnect"]
    if not isinstance(reconnect, Mapping) or reconnect.keys() != _RECONNECT_KEYS:
        raise ValueError("its reconnect policy does not have exactly its fields")
    attempts = reconnect["max_attempts"]
    return LinkProfile(
        name=_text(document, "name"),
        host=_text(document, "host"),
        port=_whole(document, "port"),
        user=_text(document, "user"),
        protocol=LinkProtocol(_text(document, "protocol")),
        key_source=KeySource(_text(document, "key_source")),
        key_file=_text(document, "key_file"),
        known_hosts=_text(document, "known_hosts"),
        connect_timeout_s=_number(document, "connect_timeout_s"),
        reconnect=ReconnectPolicy(
            first_delay_s=_number(reconnect, "first_delay_s"),
            max_delay_s=_number(reconnect, "max_delay_s"),
            factor=_number(reconnect, "factor"),
            max_attempts=None
            if attempts is None
            else _whole(reconnect, "max_attempts"),
        ),
    )


def _text(source: Mapping[str, object], key: str) -> str:
    value = source[key]
    if type(value) is not str:
        raise TypeError(f"{key} is text")
    return value


def _whole(source: Mapping[str, object], key: str) -> int:
    value = source[key]
    if type(value) is not int:
        raise TypeError(f"{key} is a whole number")
    return value


def _number(source: Mapping[str, object], key: str) -> float:
    value = source[key]
    if type(value) not in (int, float):
        raise TypeError(f"{key} is a number")
    return float(value)  # type: ignore[arg-type]
