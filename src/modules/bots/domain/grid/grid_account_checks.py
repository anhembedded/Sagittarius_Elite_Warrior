"""`EPIC-034F` — the constraints the account decides: money and permission.

Three named assertions, each reading the Connect step's `AccountView`
(`EPIC-034D`'s snapshot, narrowed) rather than the exchange:

  · `CAPITAL_ABOVE_BALANCE` — the capital is more than the account can spend
    in the quote asset, so the opening buy and the BUY levels would be
    rejected for lack of funds. It names the balance and the largest capital
    that fits;
  · `OPENING_BUY` — **the plan buys its own base** (ADR O2). The SELL levels
    sell base that Start buys at market first, out of the same capital
    (`grid_start_sequence.py`), so the account needs no base of its own and
    holding some changes nothing; the capital check covers the purchase. The
    verdict says what is bought and for about how much;
  · `KEY_CANNOT_TRADE` — the account's own `canTrade` flag is off. `None`
    (the exchange said nothing) never blocks: its own order check refuses.

Before the account was read each says it did not run, as OK, never a silent
pass (`grid_checks.py`).
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

_CENT = Decimal("0.01")


def check_capital_within_balance(inputs: GridCheckInputs) -> Verdict:
    account = inputs.account
    if account is None:
        return Verdict(
            VerdictSeverity.OK,
            "BALANCE_NOT_READ",
            "The account's balance was not read, so the capital was not compared with it",
        )
    capital = inputs.params.capital_quote
    fits = account.available_quote.quantize(_CENT, rounding=ROUND_FLOOR)
    numbers = {
        "capital": capital,
        "available": account.available_quote,
        "largest_capital": fits,
    }
    if capital > account.available_quote:
        return Verdict(
            VerdictSeverity.REFUSED,
            "CAPITAL_ABOVE_BALANCE",
            f"The capital is {capital} {account.quote_asset}, above the {fits} "
            f"{account.quote_asset} available on {account.venue_title}; "
            f"lower it to at most {fits}",
            numbers,
        )
    return Verdict(
        VerdictSeverity.OK,
        "BALANCE",
        f"The account has {fits} {account.quote_asset} available for the capital",
        numbers,
    )


def check_opening_buy(inputs: GridCheckInputs) -> Verdict:
    plan = inputs.plan
    sells = plan.sell_levels
    if not sells:
        return Verdict(
            VerdictSeverity.OK,
            "NO_OPENING_BUY",
            "No SELL level, so nothing is bought before the ladder is laid",
        )
    base, quote = plan.opening_buy_quantity, plan.opening_buy_quantity * plan.last_price
    return Verdict(
        VerdictSeverity.OK,
        "OPENING_BUY",
        f"The {len(sells)} SELL level(s) sell base the bot buys first: {base} for "
        f"about {quote.quantize(_CENT)} at market, out of the capital. The account "
        "needs no base of its own",
        {"opening_base": base, "opening_quote": quote},
    )


def check_key_may_trade(inputs: GridCheckInputs) -> Verdict:
    account = inputs.account
    if account is None:
        return Verdict(
            VerdictSeverity.OK,
            "KEY_NOT_READ",
            "The account was not read, so the key's permission to trade was not checked",
        )
    if account.can_trade is False:
        return Verdict(
            VerdictSeverity.REFUSED,
            "KEY_CANNOT_TRADE",
            f"The API key for {account.venue_title} cannot trade. Use a key with "
            "trading allowed (Tools → Options → Trading)",
        )
    if account.can_trade is None:
        return Verdict(
            VerdictSeverity.OK,
            "KEY_PERMISSION_UNKNOWN",
            "The exchange did not say whether the key may trade; its own order "
            "check decides",
        )
    return Verdict(VerdictSeverity.OK, "KEY_CAN_TRADE", "The key may trade")
