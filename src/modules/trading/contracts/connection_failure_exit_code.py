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
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
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
