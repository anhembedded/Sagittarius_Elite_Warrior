"""`EPIC-028A` — only `VenueAssembly` may construct a venue's live-trading
adapters inside `src/`.

@details `adapter_bindings.py` used to branch on `TradingVenue` once per port
(`EPIC-027G`–`027L`) and bind one instance of each for the whole process.
Two venues live at once (ADR D2/D4) makes a second construction site a
correctness bug, not a style issue: a second `InMemorySymbolOrderMetadataCache`
beside the venue's own would hand one caller stale rounding rules, and a
second `FuturesUserDataStream` would open a second socket against the same
account. `VenueAssembly` builds each part once per venue and `IVenueContexts`
hands it out; anything else asks the registry.

Scans `src/` by `ast` for a **call** to one of the classes below — an import
or a type annotation is fine. `scripts/` is not scanned on purpose: its
`epic021*_probe.py` scripts are standalone manual exercises that build one
venue's adapters without a container, never alongside the running app.

`Retire when:` the venue adapters are built by a generic, venue-keyed
factory that names no concrete class (then the factory's own guard replaces
this one).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCANNED_DIR = _REPO_ROOT / "src"

_ALLOWED_FILE = (
    _REPO_ROOT / "src" / "modules" / "trading" / "composition" / "venue_assembly.py"
)

_VENUE_ADAPTER_CLASSES = frozenset(
    {
        "EnvFirstCredentialsProvider",
        "InMemorySymbolOrderMetadataCache",
        "FuturesMetadataProvider",
        "SpotMetadataProvider",
        "FuturesTradingClientFactory",
        "SpotTradingClientFactory",
        "FuturesAccountReader",
        "SpotAccountReader",
        "FuturesUserDataStream",
        "SpotUserDataStream",
    }
)


def _constructed_venue_adapters(source: str, filename: str) -> set[str]:
    """The venue adapter classes `source` calls by name."""
    tree = ast.parse(source, filename=filename)
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _VENUE_ADAPTER_CLASSES
    }


def _construction_sites() -> dict[Path, set[str]]:
    sites: dict[Path, set[str]] = {}
    for path in sorted(_SCANNED_DIR.rglob("*.py")):
        built = _constructed_venue_adapters(path.read_text(encoding="utf-8"), str(path))
        if built:
            sites[path] = built
    return sites


def test_only_the_venue_assembly_constructs_venue_adapters() -> None:
    sites = _construction_sites()
    strays = {
        str(path.relative_to(_REPO_ROOT)): sorted(built)
        for path, built in sites.items()
        if path != _ALLOWED_FILE
    }
    assert not strays, (
        "Venue adapters constructed outside VenueAssembly (ask IVenueContexts "
        f"for the venue's own instance instead): {strays}"
    )


def test_the_venue_assembly_still_builds_every_listed_adapter() -> None:
    """Keeps the class list honest: a renamed adapter would otherwise drop
    out of the scan silently and the guard would keep passing."""
    sites = _construction_sites()

    assert sites.get(_ALLOWED_FILE) == set(_VENUE_ADAPTER_CLASSES)


def test_guard_actually_detects_a_violation() -> None:
    """Mutation-verify (`testing-rule.md` §2): fires on a call, ignores the
    annotation-only shape."""
    assert _constructed_venue_adapters(
        "cache = InMemorySymbolOrderMetadataCache()\n", "<violation-fixture>"
    ) == {"InMemorySymbolOrderMetadataCache"}
    assert not _constructed_venue_adapters(
        "def f(reader: SpotAccountReader) -> None: ...\n", "<annotation-fixture>"
    )
