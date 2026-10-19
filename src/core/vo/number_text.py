"""The pure rules that write a price or an amount of money as text (`EPIC-033N`).

Qt-free on purpose: `value_formatter.py` (the application's formatter, behind the Engine's
workbench) and the headless commands (`bots/contracts/run_earnings.py`, `BOT-192`) call the same
functions, so a figure reads the same in the Bots tab and in `bot show` and a rule changed here
changes both. A headless host installs no Qt, so this module imports nothing but the standard library.

Capability: Write a price or money amount as text without Qt
    Also: format price, format money, decimals, thousands separator, headless number text, negative zero
    Use: price_text, money_text
    User: src/modules/bots/contracts/run_earnings.py
    Status: stable
"""

from __future__ import annotations

from typing import Final

LARGE_PRICE: Final = 1_000
UNIT_PRICE: Final = 1
MAX_DECIMALS: Final = 8


def without_trailing_zeros(text: str) -> str:
    return text.rstrip("0").rstrip(".") if "." in text else text


def without_negative_zero(text: str) -> str:
    """`-0.00` is a value that rounded to zero; it reads as zero, unsigned."""
    return text[1:] if text.startswith("-") and set(text[1:]) <= set("0.,") else text


def money_text(value: float) -> str:
    """Two decimals, thousands grouped."""
    return without_negative_zero(f"{value:,.2f}")


def price_text(value: float) -> str:
    # A band is chosen by the value as the band below it would print it:
    # 999.99999 prints 1,000.0000 at four decimals, so it is a 1,000 price
    # and takes two; 0.99999999 still prints below 1 at eight, so it keeps them.
    if abs(round(value, 4)) >= LARGE_PRICE:
        return without_negative_zero(f"{value:,.2f}")
    if abs(round(value, MAX_DECIMALS)) >= UNIT_PRICE:
        return without_negative_zero(f"{value:,.4f}")
    return without_negative_zero(without_trailing_zeros(f"{value:,.{MAX_DECIMALS}f}"))
