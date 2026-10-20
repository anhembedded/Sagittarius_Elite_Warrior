"""What `trading` declares for the command line, in one call (`BOT-200`).

`key check`: which venue is this key for, asked of the exchange and kept nowhere. The
server's keys are written by `deploy/linux/sew-key`; the app only checks. A further
command of this context is one more descriptor here.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    CliCommandDescriptor,
    ICliRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.trading.cli.key_cli_handler import (
    KeyCliHandler,
)


def declare_trading_cli(registry: ICliRegistry, contributor_id: str) -> None:
    registry.declare(
        CliCommandDescriptor(
            name="key", handler=KeyCliHandler, contributor_id=contributor_id
        )
    )
