"""`EPIC-047D` — a profile as the arguments of `asyncssh.connect`, in one pure function that a test can read.

Two arguments of `asyncssh.connect` are traps, and both were met in the De-risk run (DERISK §3.3):

  · `client_keys=None` passed **explicitly** turns key login off (`PermissionDenied`); leaving the
    argument out lets asyncssh ask the agent. A profile with no key file therefore *omits* the
    argument and never maps "no file" to `None`.
  · `known_hosts=None` turns host-key verification off. The host's key is always pinned (SSH record
    D4): the file is named explicitly, and a missing one is a refusal, never a silent accept.

This module imports nothing from `asyncssh` so the trap tests run wherever the project does.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    KeySource,
    LinkProfile,
)


def known_hosts_path(profile: LinkProfile) -> Path:
    """The file that pins the host's key: the profile's own, or the user's `~/.ssh/known_hosts`."""
    chosen = profile.known_hosts or "~/.ssh/known_hosts"
    return Path(chosen).expanduser()


def connect_options(profile: LinkProfile) -> dict[str, object]:
    """The keyword arguments for `asyncssh.connect(**…)`; it never holds a secret.

    An agent profile leaves `client_keys` out, so asyncssh asks the agent **and** reads the default
    key files of `~/.ssh` (the same as OpenSSH). It cannot be narrowed to the agent alone: an empty
    list still loads the defaults and `None` turns key login off. The Options page says so."""
    options: dict[str, object] = {
        "host": profile.host,
        "port": profile.port,
        "username": profile.user,
        "known_hosts": str(known_hosts_path(profile)),
        "connect_timeout": profile.connect_timeout_s,
        "login_timeout": profile.connect_timeout_s,
        # The profile is the whole configuration: no `~/.ssh/config`, no password, no keyboard prompt.
        "config": [],
        "preferred_auth": "publickey",
    }
    if profile.key_source is KeySource.KEY_FILE:
        options["client_keys"] = [str(Path(profile.key_file).expanduser())]
        options["agent_path"] = None
    return options
