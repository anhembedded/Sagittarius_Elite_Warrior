"""`EPIC-028B` AC5 — a handler of a venue-addressed command or query reaches
a venue only through the venue the command names.

@details Every trading and strategy-arming command and query names its venue
(`venue: TradingVenue`, ADR D3). Its handler turns that into ports once, at
the top, through a venue-keyed lookup: `VenueTradingScopes`,
`IVenueContexts`, `IVenueTradingPorts` or `VenueStrategySessions`. A handler
constructed with a single venue's port, state or `TradingVenue` instead
would act on whichever venue the container bound, whatever the command
said: Emergency Stop on Spot flattening Futures. So would a handler that
asks a lookup for its `primary()` venue.

Scans every `handler.py` under the two application trees by `ast`:
- no `__init__` parameter is annotated with a name from `_SINGLE_VENUE`;
- nothing calls `.primary()`.
A helper's parameter typed `ITradingClient` is fine: the handler got that
client from the command's own venue.

`Retire when:` handlers are generated from a venue-keyed use-case registry
that injects the resolved scope itself (then that registry's own test
replaces this scan).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCANNED_DIRS = (
    _REPO_ROOT / "src" / "modules" / "trading" / "application",
    _REPO_ROOT / "src" / "modules" / "strategy" / "application" / "use_cases",
)

#: One venue's own ports and state, and the published ports still bound to
#: the primary venue until the two desks exist (`EPIC-028K`/`L`/`M`).
_SINGLE_VENUE = frozenset(
    {
        "TradingVenue",
        "IExchangeCredentialsProvider",
        "ISymbolOrderMetadataCache",
        "IMarketMetadataProvider",
        "ITradingClientFactory",
        "ITradingClient",
        "ITradingAccountReader",
        "IAccountHistoryReader",
        "ICommissionRateReader",
        "IFuturesAccountControl",
        "IUserDataStream",
        "TradingSessionState",
        "EquityCurveRecorder",
        "ITradingSession",
        "IOrderSubmission",
        "IAccountSnapshot",
        "IEquityCurve",
        "IStrategyArming",
        "LiveStrategySession",
        # One venue's bundles: a handler built with one, wired to `primary()`
        # by the composition root, acts on the primary venue whatever the
        # command names (`PR #294` review, finding 2).
        "VenueContext",
        "VenueTradingPorts",
        "VenueTradingScope",
    }
)


def _violations(source: str, filename: str) -> set[str]:
    """What `source` does that bypasses the command's own venue."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            arguments = node.args.args[1:] + node.args.kwonlyargs
            for argument in arguments:
                if argument.annotation is None:
                    continue
                found |= {
                    f"__init__({argument.arg}: {name.id})"
                    for name in ast.walk(argument.annotation)
                    if isinstance(name, ast.Name) and name.id in _SINGLE_VENUE
                }
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "primary"
        ):
            found.add(f"line {node.lineno}: .primary()")
    return found


def _handler_files() -> list[Path]:
    return sorted(path for root in _SCANNED_DIRS for path in root.rglob("handler.py"))


def test_venue_addressed_handlers_resolve_only_the_commands_venue() -> None:
    strays = {
        str(path.relative_to(_REPO_ROOT)): sorted(found)
        for path in _handler_files()
        if (found := _violations(path.read_text(encoding="utf-8"), str(path)))
    }
    assert not strays, (
        "A handler reaches a venue other than the one its command names; "
        "take VenueTradingScopes / IVenueContexts / IVenueTradingPorts / "
        f"VenueStrategySessions and look up `command.venue`: {strays}"
    )


def test_every_scanned_tree_has_handlers() -> None:
    for root in _SCANNED_DIRS:
        assert any(root.rglob("handler.py")), f"no handler.py under {root}"


def test_guard_actually_detects_a_violation() -> None:
    """Mutation-verify (`testing-rule.md` §2): fires on a single-venue
    constructor parameter, including inside `Optional`, on a single-venue
    bundle, and on `.primary()`; ignores a helper's parameter."""
    assert _violations(
        "class H:\n    def __init__(self, state: TradingSessionState) -> None: ...\n",
        "<ctor-fixture>",
    ) == {"__init__(state: TradingSessionState)"}
    assert _violations(
        "class H:\n    def __init__(self, v: TradingVenue | None) -> None: ...\n",
        "<optional-fixture>",
    ) == {"__init__(v: TradingVenue)"}
    assert _violations(
        "class H:\n    def __init__(self, ctx: VenueContext) -> None: ...\n",
        "<bundle-fixture>",
    ) == {"__init__(ctx: VenueContext)"}
    assert _violations("ctx = self._contexts.primary()\n", "<primary-fixture>") == {
        "line 1: .primary()"
    }
    assert not _violations(
        "def _close(client: ITradingClient) -> None: ...\n", "<helper-fixture>"
    )
