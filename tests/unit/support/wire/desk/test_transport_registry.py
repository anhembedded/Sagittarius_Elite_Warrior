"""`EPIC-047D` - a protocol maps to a transport in one place; an absent one is a sentence, not an ImportError."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProtocol,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    TransportMissingError,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.desk.desk_world import (
    BridgeHost,
    BridgeTransport,
)


def test_a_registered_protocol_builds_a_fresh_transport_each_time() -> None:
    registry = TransportRegistry()
    registry.register(LinkProtocol.SSH, lambda: BridgeTransport(BridgeHost()))

    first, second = registry.create(LinkProtocol.SSH), registry.create(LinkProtocol.SSH)

    assert first is not second
    assert registry.protocols() == (LinkProtocol.SSH,)


def test_a_protocol_with_no_transport_is_a_typed_sentence() -> None:
    with pytest.raises(TransportMissingError) as refused:
        TransportRegistry().create(LinkProtocol.SSH)

    assert "ssh" in refused.value.words


def test_a_transport_whose_library_is_not_installed_is_the_same_sentence() -> None:
    registry = TransportRegistry()

    def uninstalled() -> BridgeTransport:
        raise ModuleNotFoundError("no module named asyncssh")

    registry.register(LinkProtocol.SSH, uninstalled)

    with pytest.raises(TransportMissingError):
        registry.create(LinkProtocol.SSH)
