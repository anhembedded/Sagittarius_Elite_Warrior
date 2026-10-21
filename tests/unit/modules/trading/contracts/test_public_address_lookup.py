"""`BOT-224` — a lookup is an address or a reason, never both and never neither."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.public_address_lookup import (
    PublicAddressFailure,
    PublicAddressLookup,
)


def test_a_found_lookup_has_an_address_and_no_failure() -> None:
    lookup = PublicAddressLookup.found("93.184.216.34")

    assert (lookup.address, lookup.failure) == ("93.184.216.34", None)


def test_a_failed_lookup_has_a_failure_and_no_address() -> None:
    lookup = PublicAddressLookup.failed(PublicAddressFailure.UNREACHABLE)

    assert (lookup.address, lookup.failure) == (None, PublicAddressFailure.UNREACHABLE)


def test_a_lookup_with_both_or_neither_cannot_be_built() -> None:
    with pytest.raises(ValueError):
        PublicAddressLookup("93.184.216.34", PublicAddressFailure.UNREACHABLE)
    with pytest.raises(ValueError):
        PublicAddressLookup()
