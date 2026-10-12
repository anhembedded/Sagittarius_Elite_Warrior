"""The one answer to "which exit code does this connection failure deserve" (`EPIC-038` D9).

`exchange-status` and `preflight` both end a command with a code a supervisor
keys its restart policy on, so the mapping from `ConnectionFailureKind` exists
once, here, and both read it.

**The rule is whether a restart can fix it.**

  * 5 `CONFIGURATION`: the operator must change something, so a restart only
    repeats the refused request (and risks an IP ban): no key, a key the
    exchange rejects (`-2015`: key, address or permission), a bad signature
    (`-1022`), a key that can withdraw, Hedge Mode.
  * 6 `EXCHANGE`: the fault is out there or will pass, so a restart with a delay
    is right: a timeout, a refused connection, a 5xx or maintenance page, and a
    rejected timestamp (`-1021`), which resyncs.

A preflight check that finds a fault of the machine itself (disk, data root,
Python, a measured clock skew beyond the threshold) is neither: it exits
`PREFLIGHT_FAILED` (4), decided by the check, not here.

`test_every_failure_kind_has_an_exit_code` fails for a kind added without a row.

**Three entrances, one rule.** A command meets a failure as a connection status
(`EXIT_CODE_FOR_FAILURE`), as a named order rejection
(`exit_code_of_order_rejection`) or as a raw Binance exception
(`exit_code_of_binance_error`); the last two read the same facts as the first, and
`test_the_three_entrances_agree` pins that they cannot drift apart.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_error_codes import (
    OPERATOR_FIXABLE_CODES,
)

EXIT_CODE_FOR_FAILURE: dict[ConnectionFailureKind, ExitCode] = {
    ConnectionFailureKind.NOT_CONFIGURED: ExitCode.CONFIGURATION,
    ConnectionFailureKind.WITHDRAWAL_ENABLED: ExitCode.CONFIGURATION,
    ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: ExitCode.CONFIGURATION,
    ConnectionFailureKind.BAD_SIGNATURE: ExitCode.CONFIGURATION,
    ConnectionFailureKind.KEY_REJECTED: ExitCode.CONFIGURATION,
    ConnectionFailureKind.CLOCK_SKEW: ExitCode.EXCHANGE,
    ConnectionFailureKind.NETWORK: ExitCode.EXCHANGE,
    ConnectionFailureKind.MAINTENANCE: ExitCode.EXCHANGE,
}


def exit_code_of_order_rejection(reason: OrderRejectionReason) -> ExitCode:
    """A refused order: the key itself rejected is the operator's (5); any other
    refusal is the exchange's answer to this order (6), as it always was."""
    if reason is OrderRejectionReason.KEY_REJECTED:
        return EXIT_CODE_FOR_FAILURE[ConnectionFailureKind.KEY_REJECTED]
    return ExitCode.EXCHANGE


def exit_code_of_binance_error(code: int | None) -> ExitCode:
    """A raw Binance exception that no layer translated: the codes only the
    operator can fix (`-2015`, `-2008`, `-2014`, `-1022`) are 5, everything else
    (`-1021`, a gateway page, any other code) is 6."""
    if code in OPERATOR_FIXABLE_CODES:
        return ExitCode.CONFIGURATION
    return ExitCode.EXCHANGE
