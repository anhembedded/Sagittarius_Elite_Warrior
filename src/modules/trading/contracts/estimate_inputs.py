"""`EPIC-028G` — the input checks every order estimate makes.

@details An estimate built on NaN, infinity or a negative amount would still
print as a number, and a number on the order form reads as exact. So every
estimate refuses such input with `ValueError`, through these three checks.
"""

from __future__ import annotations

from decimal import Decimal


def require_finite(name: str, value: Decimal) -> None:
    """@throws ValueError `value` is NaN or infinite."""
    if not value.is_finite():
        raise ValueError(f"{name} must be a finite number, got {value}")


def require_not_negative(name: str, value: Decimal) -> None:
    """@throws ValueError `value` is not finite, or below zero."""
    require_finite(name, value)
    if value < 0:
        raise ValueError(f"{name} cannot be negative, got {value}")


def require_positive(name: str, value: Decimal) -> None:
    """@throws ValueError `value` is not finite, or not above zero."""
    require_finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero, got {value}")
