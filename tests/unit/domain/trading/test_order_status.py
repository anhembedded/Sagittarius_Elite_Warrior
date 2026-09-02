import pytest
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import (
    OrderStatus,
    is_valid_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED),
        (OrderStatus.NEW, OrderStatus.FILLED),
        (OrderStatus.NEW, OrderStatus.CANCELED),
        (OrderStatus.NEW, OrderStatus.REJECTED),
        (OrderStatus.NEW, OrderStatus.EXPIRED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCELED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.EXPIRED),
    ],
)
def test_valid_transitions_are_allowed(
    current: OrderStatus, target: OrderStatus
) -> None:
    assert is_valid_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        # The exact nonsensical case the task names: a filled order cannot
        # become new again.
        (OrderStatus.FILLED, OrderStatus.NEW),
        (OrderStatus.CANCELED, OrderStatus.NEW),
        (OrderStatus.REJECTED, OrderStatus.NEW),
        (OrderStatus.EXPIRED, OrderStatus.NEW),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.NEW),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.REJECTED),
        (OrderStatus.NEW, OrderStatus.NEW),
        (OrderStatus.FILLED, OrderStatus.FILLED),
    ],
)
def test_invalid_transitions_are_blocked(
    current: OrderStatus, target: OrderStatus
) -> None:
    assert not is_valid_transition(current, target)


@pytest.mark.parametrize(
    "terminal",
    [
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    ],
)
def test_terminal_statuses_have_no_outgoing_transition(terminal: OrderStatus) -> None:
    assert all(not is_valid_transition(terminal, target) for target in OrderStatus)
