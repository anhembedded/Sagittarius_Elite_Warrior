"""`EPIC-047C` — the bridge: the process `sshd` starts for each session behind a forced-command key.

`python -m Sagittarius_Elite_Warrior.src.shell.link_bridge_main`, started by `deploy/linux/sew-bridge`
as the `sew` account, with the data root in `SEW_DATA_ROOT`. It speaks the remote link's protocol on
standard input and output (`support/wire/bridge/bridge_session.py`), reads the bots' files, the
host-facts file, the host's market-data and host-reads files and its candle store (read-only), and sends commands
through the host's control directory. It opens no socket, loads no key and calls no exchange: nothing it imports can (`tests/unit/support/wire/bridge/`).

**Slim by construction.** It imports the wire layer, the three modules' `link.py` files (the stores'
readers and the control-door writer) and the lock probe, and never `composition_root`, `main.py`,
the Engine's `App` or a Qt module; `test_the_bridge_imports_no_application` holds that, and the
import time on the VPS is recorded in the task (`EPIC-047C`, acceptance criteria).

Exit status: `0` the session ended, `3` refused (a different build), `4` a protocol violation,
`5` a failure nobody planned for (logged with its traceback), `6` the idle watchdog ended it
(`bridge_protocol.py`).
"""

from __future__ import annotations

import logging
import sys

from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.modules.bots.link import bridge_bots
from Sagittarius_Elite_Warrior.src.modules.market_data.link import bridge_candles
from Sagittarius_Elite_Warrior.src.modules.operations.link import (
    bridge_documents,
    bridge_door,
    bridge_facts,
)
from Sagittarius_Elite_Warrior.src.shell.link_version import link_app_version
from Sagittarius_Elite_Warrior.src.shell.wire_roots import link_roots
from Sagittarius_Elite_Warrior.src.support.instance_lock.instance_probe import (
    FileLockInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_runner import serve
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_session import (
    SessionPorts,
)

logger = logging.getLogger("App.LinkBridge")

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def main() -> int:
    _log_to_stderr()
    state = data_root() / "state"
    roots = link_roots()
    ports = SessionPorts(
        bots=bridge_bots(state / "bots"),
        facts=bridge_facts(state),
        door=bridge_door(state, FileLockInstanceProbe(state / "instance.lock")),
        documents=bridge_documents(state, roots),
        candles=bridge_candles(data_root() / "database"),
    )
    sys.stdin.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")  # type: ignore[union-attr]
    logger.info("[link-bridge] serving data root %s", data_root())
    return serve(sys.stdin, sys.stdout, roots, link_app_version(), ports)


def _log_to_stderr() -> None:
    """Standard output is the protocol; the log goes to standard error, where `sshd` hands it to the desktop."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    app_logger = logging.getLogger("App")
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


if __name__ == "__main__":
    sys.exit(main())
