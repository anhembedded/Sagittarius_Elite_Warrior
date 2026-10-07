"""The walk and the scans `test_mainnet_has_no_order_path.py` and its probes use
(`EPIC-034E`): what trades, where the read-only mainnet source starts, how an
import chain and an order call are found. Helpers only: no test lives here."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    imported_modules,
    runtime_nodes,
    strip_prefix,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"

#: Where the mainnet read-only source lives, and what it is built from.
START_FILES = (
    "modules/bots/application/queries/get_mainnet_account/handler.py",
    "modules/bots/application/queries/get_mainnet_account/query.py",
    "modules/bots/ui/bots_screen/mainnet_account_text.py",
    "support/binance_gateway/contracts/i_mainnet_read_client.py",
    "support/binance_gateway/contracts/i_credentials_resolver.py",
    "support/binance_gateway/contracts/account_source.py",
)

#: What trades, by dotted module name relative to `src/`. A module whose name
#: is one of these, or starts with one followed by a dot, is forbidden.
FORBIDDEN = (
    "modules.trading.adapters.binance.spot.spot_session_factory",
    "modules.trading.adapters.binance.spot.spot_trading_client",
    "modules.trading.adapters.binance.spot.spot_trading_client_factory",
    "modules.trading.adapters.binance.futures_session_factory",
    "modules.trading.adapters.binance.futures_trading_client",
    "modules.trading.adapters.binance.futures_trading_client_factory",
    "support.binance_gateway.contracts.i_spot_session_factory",
    "support.binance_gateway.contracts.i_trading_session_factory",
    "modules.trading.contracts.i_trading_client",
    "modules.trading.contracts.i_trading_client_factory",
    "modules.trading.contracts.i_order_submission",
    "modules.trading.contracts.i_trading_session",
    "modules.trading.application.orders",
    "modules.trading.application.session",
)

#: Every read the mainnet client may make. A new member is a reviewed change.
READS = frozenset(
    {
        "ping",
        "get_server_time",
        "get_account",
        "get_account_api_permissions",
        "get_open_orders",
        "get_orderbook_ticker",
        "get_exchange_info",
    }
)


#: The only file of the mainnet package that may construct python-binance's `Client`.
SESSION_FACTORY_FILE = "mainnet_read_session_factory.py"


def is_forbidden(module: str) -> bool:
    return any(module == f or module.startswith(f + ".") for f in FORBIDDEN)


def file_of(module: str) -> Path | None:
    base = SRC.joinpath(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def source_in_repo(module: str) -> str | None:
    path = file_of(module)
    return path.read_text(encoding="utf-8") if path is not None else None


def path_to_an_order(
    starts: list[str], source_of: Callable[[str], str | None]
) -> list[str] | None:
    """The shortest import chain from a start module to a forbidden one, or
    `None`. A module `source_of` cannot read (the engine, the standard
    library) ends the chain: only this repository's modules can trade here."""
    parents: dict[str, str | None] = {start: None for start in starts}
    queue = list(starts)
    while queue:
        module = queue.pop(0)
        if is_forbidden(module):
            return chain_to(module, parents)
        source = source_of(module)
        if source is None:
            continue
        for imported in sorted(executed_by(module, source)):
            if imported not in parents:
                parents[imported] = module
                queue.append(imported)
    return None


def prefixes(module: str) -> set[str]:
    """`a.b.c` runs `a` and `a.b` first: every ancestor package."""
    parts = module.split(".")
    return {".".join(parts[:end]) for end in range(1, len(parts))}


def executed_by(module: str, source: str) -> set[str]:
    """Every module that importing `module` runs, by its own source: what it
    imports, the packages above each of those and above itself, and the
    submodule a `from pkg import name` may name."""
    found = set(imported_modules(module, source)) | prefixes(module)
    for node in runtime_nodes(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            base = strip_prefix(node.module)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    for imported in list(found):
        found |= prefixes(imported)
    return found


#: An attribute call that places, tests or cancels an order on python-binance's
#: `Client`: `create_order`, `create_test_order`, `cancel_order`,
#: `cancel_all_open_orders`, `order_limit_buy`, `order_oco_sell`, `create_oco_order`...
ORDER_CALL = re.compile(
    r"^(create|cancel|new|test|place|post)_\w*(order|oco)\w*$|^order_\w+$"
)


def order_call_sites(
    source: str, filename: str, *, may_build_client: bool
) -> list[str]:
    """Each place `source` calls something that orders, or builds a python-binance
    client where only the session factory may."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Attribute) and ORDER_CALL.match(node.attr):
            found.append(f"{filename}:{node.lineno} .{node.attr}")
        if (
            isinstance(node, ast.ImportFrom)
            and not may_build_client
            and node.module
            and node.module.split(".")[0] == "binance"
        ):
            found.extend(
                f"{filename}:{node.lineno} imports {node.module}"
                for alias in node.names
                if node.module == "binance.client" or alias.name == "Client"
            )
        if isinstance(node, ast.Import) and not may_build_client:
            found.extend(
                f"{filename}:{node.lineno} imports {alias.name}"
                for alias in node.names
                if alias.name.split(".")[0] == "binance"
            )
    return found


def chain_to(end: str, parents: dict[str, str | None]) -> list[str]:
    chain = [end]
    while (parent := parents[chain[-1]]) is not None:
        chain.append(parent)
    return chain[::-1]


def start_modules() -> list[str]:
    files = [SRC / entry for entry in START_FILES]
    mainnet = SRC / "modules" / "trading" / "adapters" / "binance" / "mainnet"
    files.extend(sorted(mainnet.glob("*.py")))
    return [
        ".".join(path.relative_to(SRC).with_suffix("").parts)
        for path in files
        if path.name != "__init__.py"
    ]
