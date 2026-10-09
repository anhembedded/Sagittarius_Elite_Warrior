"""`EPIC-034F` — the constraints the account decides: money and permission.

Two named assertions, each reading the Connect step's `AccountView`
(`EPIC-034D`'s snapshot, narrowed) rather than the exchange. The balance is not
one of them: whether the account can pay for the ladder is a rule over the
exchange's own snapshot (`BOT-173`, `exchange_rules.quote_short_for_ladder`),
judged with the plan's exact need and the same words at the screen and at Start.

  · `OPENING_BUY` — **the plan buys its own base** (ADR O2). The SELL levels
    sell base that Start buys at market first, out of the same capital
    (`grid_start_sequence.py`), so the account needs no base of its own and
    holding some changes nothing; the quote rule covers the purchase. The
    verdict says what is bought and for about how much;
  · `KEY_CANNOT_TRADE` — the account's own `canTrade` flag is off. `None`
    (the exchange said nothing) never blocks: its own order check refuses.

Before the account was read each says it did not run, as OK, never a silent
pass (`grid_checks.py`).
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

_CENT = Decimal("0.01")


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
