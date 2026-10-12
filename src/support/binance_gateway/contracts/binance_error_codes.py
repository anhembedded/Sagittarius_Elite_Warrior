"""The Binance error codes whose meaning decides what to do next, named once.

`EPIC-038` D9. Three places read the same facts: the connection check files a code
under a `ConnectionFailureKind`, the order translator under an
`OrderRejectionReason`, and a command-line command that meets a raw exception
chooses an exit code. They agree because they read these sets instead of
retyping the numbers.

Verification note: written from Binance's documented errors and the owner's logs
(`BUG-175`), not re-checked against a live call.
"""

from __future__ import annotations

#: The exchange does not know the key: `-2008` Invalid Api-Key ID (a testnet key on
#: mainnet, or the reverse), `-2014` API-key format invalid.
UNKNOWN_KEY_ID_CODE = -2008
KEY_FORMAT_CODE = -2014
UNKNOWN_KEY_CODES = frozenset({UNKNOWN_KEY_ID_CODE, KEY_FORMAT_CODE})

#: Every code that says the exchange rejects the API key itself: the unknown-key
#: codes and `-2015` (it knows the key and refuses this request: an address off
#: the key's allowlist, or a missing permission).
KEY_REJECTED_CODE = -2015
KEY_REJECTED_CODES = frozenset({KEY_REJECTED_CODE, *UNKNOWN_KEY_CODES})

#: `-1022`: the request's signature does not verify (a mistyped or truncated secret).
BAD_SIGNATURE_CODE = -1022

#: `-1021`: the timestamp is outside the receive window. The clock can resync, so
#: unlike the codes above a restart can outlast it.
CLOCK_SKEW_CODE = -1021

#: The codes only the operator can fix; a restart repeats the refused request.
OPERATOR_FIXABLE_CODES = frozenset({*KEY_REJECTED_CODES, BAD_SIGNATURE_CODE})
