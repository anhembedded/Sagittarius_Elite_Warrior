"""`EPIC-047D` - the build offers SSH for the SSH protocol, and a transport is named, not imported, at boot."""

from __future__ import annotations

import sys

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import LinkProtocol
from Sagittarius_Elite_Warrior.src.support.wire.desk.default_transports import (
    SSH_TRANSPORT,
    build_transport_registry,
)


def test_every_protocol_a_profile_can_name_has_a_transport() -> None:
    assert set(build_transport_registry().protocols()) == set(LinkProtocol)


def test_the_ssh_transport_is_named_by_path_and_building_the_registry_imports_no_ssh_library() -> (
    None
):
    sys.modules.pop("asyncssh", None)

    build_transport_registry()

    assert SSH_TRANSPORT.target.endswith(":AsyncSshTransport")
    assert "asyncssh" not in sys.modules
