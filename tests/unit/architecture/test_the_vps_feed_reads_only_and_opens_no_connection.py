"""`EPIC-047H` - what the host serves the VPS tab places nothing, cancels nothing, holds no key and opens no connection of its own.

**Why.** The recorder, the refresher and the files they write run on the real-money host, on the IP the bots trade
on (decision record 2026-10-27, D2/D3/D4). The decision's promise is that they add *reads* under a ceiling, at
routine priority, and nothing that touches an order, a lease, a limit or a key; and that the recorder reuses the
host's one exchange client and the stream it already holds. A test that runs them proves their behaviour; this proves
what they *cannot* do, because the names are not in their imports: no exchange client, no network library, no order
or session port, no credentials. A new file of the feed is added to `_FEED_FILES` with the same rule, or it is not
part of the feed.

Retire when: the feed's files are held by a package boundary the module guard states (a `vps_feed` package).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPERATIONS = "src/modules/operations/application"
_FEED_FILES = (
    f"{_OPERATIONS}/candle_fold.py",
    f"{_OPERATIONS}/document_publisher.py",
    f"{_OPERATIONS}/facts_refreshing.py",
    f"{_OPERATIONS}/market_recorder.py",
    f"{_OPERATIONS}/refresh_facts_outcome.py",
    f"{_OPERATIONS}/vps_facts_refresher.py",
    f"{_OPERATIONS}/vps_refresh_budget.py",
    f"{_OPERATIONS}/vps_refresh_costs.py",
    f"{_OPERATIONS}/vps_refresh_report.py",
    f"{_OPERATIONS}/vps_refresh_work.py",
    f"{_OPERATIONS}/vps_weight_ledger.py",
    "src/modules/operations/adapters/wire_document_file.py",
    "src/modules/operations/composition/vps_feed_bindings.py",
    "src/modules/operations/composition/vps_feed_host.py",
    "src/modules/bots/application/services/host_reads/exchange_bot_read_refresh.py",
    "src/modules/bots/adapters/latest_exchange_reads.py",
    "src/modules/bots/adapters/held_host_exchange_reads.py",
    "src/modules/market_data/adapters/bridge_candles.py",
    "src/modules/market_data/adapters/persistence/readonly_candle_shards.py",
    "src/modules/trading/adapters/memory_mark_board.py",
    "src/modules/trading/adapters/binance/policy_weight_meter.py",
)
#: Top-level packages that open a connection or speak HTTP.
_NETWORK = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib",
        "ftplib",
        "smtplib",
        "websockets",
        "aiohttp",
        "requests",
        "httpx",
        "binance",
    }
)
#: Module paths a feed file may not import from: adapters that build clients, and the gateway's.
_FORBIDDEN_PREFIXES = (
    "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_sessions",
    "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory",
    "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot",
    "Sagittarius_Elite_Warrior.src.modules.market_data.adapters",
    "Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters",
)
#: Names that place, cancel, hold a lease or a key: a feed file imports none of them.
_FORBIDDEN_NAMES = frozenset(
    {
        "IOrderSubmission",
        "ITradingClient",
        "ITradingClientFactory",
        "ITradingSession",
        "ITradingSessionFactory",
        "IExchangeCredentialsProvider",
        "ExchangeCredentials",
        "IVenueKeyStates",
        "IMarketStream",
        "ILiveStreamService",
    }
)


def breaches(source: str, path: str) -> list[str]:
    """What `source` imports that a feed file may not."""
    found: list[str] = []
    own = "Sagittarius_Elite_Warrior." + path.removesuffix(".py").replace("/", ".")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
            names: list[str] = []
        elif isinstance(node, ast.ImportFrom):
            modules, names = [node.module or ""], [alias.name for alias in node.names]
        else:
            continue
        for module in modules:
            if module.split(".")[0] in _NETWORK:
                found.append(f"{path}: imports the network library {module}")
            # a file inside a forbidden package (the store reader beside the store) may name its neighbours
            if module.startswith(_FORBIDDEN_PREFIXES) and not any(
                own.startswith(prefix) and module.startswith(prefix)
                for prefix in _FORBIDDEN_PREFIXES
            ):
                found.append(f"{path}: imports the client-building module {module}")
        found += [
            f"{path}: imports {name}, which acts on an order, a session or a key"
            for name in names
            if name in _FORBIDDEN_NAMES
        ]
    return found


def _feed_files() -> list[str]:
    """The named files, and every `vps_*.py` of the operations module: a new file of the feed cannot be left out."""
    found = {
        path.relative_to(_REPO_ROOT).as_posix()
        for path in (_REPO_ROOT / "src/modules/operations/application").glob("vps_*.py")
    }
    return sorted(found | set(_FEED_FILES))


def test_no_file_of_the_feed_can_place_an_order_hold_a_key_or_open_a_connection() -> (
    None
):
    problems: list[str] = []
    for relative in _feed_files():
        source = (_REPO_ROOT / relative).read_text(encoding="utf-8")
        problems += breaches(source, relative)

    assert problems == []


def test_every_file_of_the_feed_exists() -> None:
    assert [p for p in _FEED_FILES if not (_REPO_ROOT / p).is_file()] == []
    assert len(_feed_files()) >= len(_FEED_FILES)


def test_the_scanner_can_fail() -> None:
    assert breaches("import socket\n", "x")
    assert breaches("from binance.client import Client\n", "x")
    assert breaches(
        "from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import IOrderSubmission\n",
        "x",
    )
    assert breaches(
        "from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.client import C\n",
        "x",
    )
    assert breaches("import json\nfrom pathlib import Path\n", "x") == []
