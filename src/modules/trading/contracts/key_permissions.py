"""`EPIC-034` D5 — what an API key may do, as the exchange says it
(`GET /sapi/v1/account/apiRestrictions`).

@details Only what the key gate decides on: a key that can withdraw is refused
(D5), whatever else it can do; trading keys are accepted, because mainnet trades
exactly like testnet (D11). Each flag must be a boolean in the answer: the parser
raises when the exchange leaves one out, never a guessed `False`, because "cannot
withdraw" is the one thing the gate must be sure of (`code/errors.md` #7).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyPermissions:
    can_read: bool
    can_trade_spot: bool
    can_withdraw: bool
