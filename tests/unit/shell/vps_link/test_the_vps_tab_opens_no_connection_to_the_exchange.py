"""`EPIC-047E` (AC10, decision record 2026-10-27 D1/D7b) - the VPS tab's backend makes no connection to Binance.

The static guard (`test_the_vps_tab_reaches_no_binance_client.py`) reads imports; this proves the same at run time, in two
ways. A clean interpreter that imports the tab's backend loads no exchange client and no network library. And a whole
session over the real bridge session - snapshot, events, every query the Bots screen asks, a command - opens no socket
beyond the loopback: a recorder stands where a connection would be made and is shown to catch one first.
The Bots tab beside it, which does read the exchange, is the contrast: `test_the_vps_tab_asks_no_exchange_where_the_bots_tab_does.py`.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_exchange_facts import (
    GetExchangeFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_choices import (
    GetVenueChoicesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_connection import (
    GetVenueConnectionQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import (
    BTC,
    ask,
    build_dispatcher,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import VpsTabWorld

_PARENT = Path(__file__).resolve().parents[5]
_LOOPBACK = ("127.", "::1", "localhost")
_FORBIDDEN_AT_RUN_TIME = (
    "binance",
    "websockets",
    "aiohttp",
    "requests",
    "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance",
    "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance",
    "Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters",
)


def test_a_clean_interpreter_that_imports_the_backend_loads_no_exchange_client() -> (
    None
):
    code = (
        "import sys\n"
        "import Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_control\n"
        "import Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_world\n"
        "import Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_command_dispatcher\n"
        f"bad = [m for m in sys.modules if m.split('.')[0] in {_FORBIDDEN_AT_RUN_TIME[:4]!r}"
        f" or m.startswith({_FORBIDDEN_AT_RUN_TIME[4:]!r})]\n"
        "print('LOADED', sorted(bad))\n"
    )
    env = {**os.environ, "PYTHONPATH": str(_PARENT), "QT_QPA_PLATFORM": "offscreen"}

    done = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )

    assert done.stdout.strip().splitlines()[-1] == "LOADED []"


class _Recorder:
    """Stands where `socket.socket.connect` is; remembers every address it is asked for."""

    def __init__(self) -> None:
        self.addresses: list[str] = []

    def connect(self, address: object) -> None:
        host = str(address[0]) if isinstance(address, tuple) else str(address)
        self.addresses.append(host)
        raise OSError("the test refuses every connection")

    def non_loopback(self) -> list[str]:
        return [a for a in self.addresses if not a.startswith(_LOOPBACK)]


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Recorder]:
    found = _Recorder()
    monkeypatch.setattr(socket.socket, "connect", found.connect)
    yield found


def test_the_recorder_catches_a_connection_to_the_outside(recorder: _Recorder) -> None:
    with pytest.raises(OSError, match="refuses every connection"):
        socket.create_connection(("192.0.2.1", 443), timeout=1)

    assert recorder.non_loopback() == ["192.0.2.1"]


def test_a_whole_session_opens_no_connection_to_the_outside(
    recorder: _Recorder,
) -> None:
    tab = VpsTabWorld().start()
    dispatcher, _ = build_dispatcher(tab)
    asked: list[object] = [
        ListBotsQuery(),
        GetBotFillsQuery(BTC.bot_id),
        GetExchangeFactsQuery(BTC.bot_id),
        GetPlannerMarketQuery(BTC.venue, BTC.symbol),
        GetVenueChoicesQuery(),
        GetVenueConnectionQuery(BTC.venue, BTC.symbol),
    ]
    for query in asked:
        ask(dispatcher, query)
    dispatcher.dispatch(
        StopBotCommand, StopBotCommand(BTC.bot_id, ExposureHandling.KEEP)
    )
    tab.stop()

    assert recorder.non_loopback() == []
