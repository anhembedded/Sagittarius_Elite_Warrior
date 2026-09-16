"""`OrderIntent` is the **one** type both order paths produce.

Two things decide an order's `(side, reduce_only)` pair in this application — a
strategy's `SignalAction` and a human's Long/Short click against the account's
real position — and the pair itself is trading's published vocabulary. Until
`EPIC-025` PR 2.1a they both returned a dataclass declared inside
`domain/policies/signal_action_to_order_intent.py`, which put a published type
in a policy file and cost `OrderRequest` its name (`order_request.py`'s own
docstring records the collision).

These tests pin the outcome of that split rather than the mapping tables, which
`test_signal_action_to_order_intent.py` and `test_manual_order_intent.py`
already cover row by row. What could regress here is **identity**: a future edit
re-declaring `OrderIntent` beside one of the two producers would leave every
mapping test green while the two paths returned different types, and anything
treating them interchangeably — `IOrderSubmission`'s callers do — would start
failing at a distance from the edit.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_intent import (
    OrderIntent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
    manual_order_intent_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.signal_action_to_order_intent import (
    order_intent_for,
)


def test_both_producers_return_the_published_type() -> None:
    """`is` on the class, not `isinstance`: two structurally identical
    dataclasses both satisfy `isinstance` against themselves, so only class
    identity catches a second declaration."""
    from_signal = order_intent_for(SignalAction.BUY)
    from_click = manual_order_intent_for(ManualOrderDirection.LONG, None)

    assert type(from_signal) is OrderIntent
    assert type(from_click) is OrderIntent


def test_the_two_paths_agree_where_they_describe_the_same_order() -> None:
    """A strategy's BUY and a click on Long against a flat account are the same
    order — `OrderSide.BUY`, opening. They are produced by different tables, so
    an equality here is a real cross-check rather than a tautology, and it only
    holds because both tables answer in one type."""
    assert order_intent_for(SignalAction.BUY) == manual_order_intent_for(
        ManualOrderDirection.LONG, None
    )


def test_the_pair_is_frozen() -> None:
    """It crosses a module boundary to two consumers outside this module, so one
    of them must not be able to edit what the other sees. `FrozenInstanceError`
    rather than `AttributeError`, which is its base class: the narrower name is
    what the repository's other frozen-contract tests assert
    (`tests/unit/modules/trading/domain/test_order.py`), and a plain
    `AttributeError` would also pass for a misspelled field name."""
    intent = OrderIntent(side=OrderSide.BUY, reduce_only=False)

    with pytest.raises(FrozenInstanceError):
        intent.reduce_only = True  # type: ignore[misc]
