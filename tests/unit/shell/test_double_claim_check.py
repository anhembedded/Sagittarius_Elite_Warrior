"""Two modules may not own the same abstract type (SDD boot step 4).

Why this is a test and not a comment: the container's second registration wins
silently, so the bug reads as "my adapter is not being used" and gets debugged
in the wrong file entirely. The check runs before `boot()`, so nothing has
resolved yet and the message can still name both modules.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.shell.double_claim_check import (
    DoubleClaimCheck,
    DoubleClaimError,
)


class IKlines:
    pass


class IOrders:
    pass


def test_one_module_claiming_one_type_is_fine() -> None:
    check = DoubleClaimCheck()
    check.record("market_data", [IKlines])
    assert check.owner_of(IKlines) == "market_data"


def test_the_same_module_registering_twice_is_fine() -> None:
    """A module that re-registers its own type is overriding itself, which is
    its business — only a *second* module is the ambiguity."""
    check = DoubleClaimCheck()
    check.record("market_data", [IKlines])
    check.record("market_data", [IKlines])
    assert check.owner_of(IKlines) == "market_data"


def test_different_types_from_different_modules_are_fine() -> None:
    check = DoubleClaimCheck()
    check.record("market_data", [IKlines])
    check.record("trading", [IOrders])
    assert check.owner_of(IKlines) == "market_data"
    assert check.owner_of(IOrders) == "trading"
    assert set(check.claimed_types()) == {IKlines, IOrders}


def test_a_second_module_claiming_the_same_type_fails() -> None:
    check = DoubleClaimCheck()
    check.record("market_data", [IKlines])

    with pytest.raises(DoubleClaimError) as failure:
        check.record("trading", [IOrders, IKlines])

    message = str(failure.value)
    assert "IKlines" in message
    assert "market_data" in message
    assert "trading" in message
    assert "contracts/" in message, "the message must say where the fix lives"
