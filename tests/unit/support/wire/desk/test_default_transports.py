"""`EPIC-047D` - a build that has no SSH adapter says so in words when a profile asks for SSH."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import LinkProtocol
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    TransportMissingError,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.default_transports import (
    build_transport_registry,
)


def test_a_build_without_an_ssh_adapter_answers_a_profile_in_words() -> None:
    with pytest.raises(TransportMissingError) as missing:
        build_transport_registry().create(LinkProtocol.SSH)

    assert "ssh" in missing.value.words
