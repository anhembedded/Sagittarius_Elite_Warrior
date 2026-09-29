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

Scans `src/` by `ast` for a **call** to one of the classes below — by bare
name, as `module.Class(...)` or through an `import ... as` alias; an import or
a type annotation is fine. Besides the adapters it guards the per-venue state
(`TradingSessionState`, `EquityCurveRecorder`, built only by `VenueAssembly`)
and the registry (`VenueAssembly`, `VenueContexts`, built only by
`adapter_bindings.py`). `scripts/` is not scanned on purpose: its
`epic021*_probe.py` scripts are standalone manual exercises that build one
venue's adapters without a container, never alongside the running app.

`Retire when:` the venue adapters are built by a generic, venue-keyed
factory that names no concrete class (then the factory's own guard replaces
this one).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCANNED_DIR = _REPO_ROOT / "src"

_COMPOSITION_DIR = _REPO_ROOT / "src" / "modules" / "trading" / "composition"
_VENUE_ASSEMBLY_FILE = _COMPOSITION_DIR / "venue_assembly.py"
_ADAPTER_BINDINGS_FILE = _COMPOSITION_DIR / "adapter_bindings.py"

# The per-venue state is guarded with the adapters: a second
# `TradingSessionState` beside the venue's own is a venue whose kill switch and
# daily counters are not the ones its user data stream updates.
_VENUE_STATE_CLASSES = frozenset({"TradingSessionState", "EquityCurveRecorder"})

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

# The registry and the assemblies it hands out: `adapter_bindings.py` is the
# one place that builds them, so a second `VenueAssembly` cannot appear beside
# the one `VenueContexts` caches per venue.
_REGISTRY_CLASSES = frozenset({"VenueAssembly", "VenueContexts"})

_GUARDED_CLASSES = _VENUE_ADAPTER_CLASSES | _VENUE_STATE_CLASSES | _REGISTRY_CLASSES

_ALLOWED: dict[Path, frozenset[str]] = {
    _VENUE_ASSEMBLY_FILE: _VENUE_ADAPTER_CLASSES | _VENUE_STATE_CLASSES,
    _ADAPTER_BINDINGS_FILE: _REGISTRY_CLASSES,
}


def _constructed_venue_adapters(source: str, filename: str) -> set[str]:
    """The guarded classes `source` calls, by bare name, by attribute
    (`module.Class(...)`) or through an `import ... as` alias."""
    tree = ast.parse(source, filename=filename)
    aliases = {
        alias.asname: alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.asname
    }
    built: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = aliases.get(node.func.id, node.func.id)
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue
        if name in _GUARDED_CLASSES:
            built.add(name)
    return built


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
        str(path.relative_to(_REPO_ROOT)): sorted(
            built - _ALLOWED.get(path, frozenset())
        )
        for path, built in sites.items()
        if built - _ALLOWED.get(path, frozenset())
    }
    assert not strays, (
        "Venue adapters, per-venue state or the venue registry constructed "
        "outside their one builder (ask IVenueContexts for the venue's own "
        f"instance instead): {strays}"
    )


def test_each_builder_still_builds_every_class_it_is_allowed_to() -> None:
    """Keeps the class lists honest: a renamed class would otherwise drop out
    of the scan silently and the guard would keep passing."""
    sites = _construction_sites()

    assert sites.get(_VENUE_ASSEMBLY_FILE) == _ALLOWED[_VENUE_ASSEMBLY_FILE]
    assert sites.get(_ADAPTER_BINDINGS_FILE) == _ALLOWED[_ADAPTER_BINDINGS_FILE]


def test_guard_actually_detects_a_violation() -> None:
    """Mutation-verify (`testing-rule.md` §2): fires on a call however it is
    spelled, ignores the annotation-only shape."""
    assert _constructed_venue_adapters(
        "cache = InMemorySymbolOrderMetadataCache()\n", "<violation-fixture>"
    ) == {"InMemorySymbolOrderMetadataCache"}
    assert not _constructed_venue_adapters(
        "def f(reader: SpotAccountReader) -> None: ...\n", "<annotation-fixture>"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("reader = adapters.FuturesAccountReader(a, b)\n", {"FuturesAccountReader"}),
        (
            "from x import SpotUserDataStream as Stream\nStream(a)\n",
            {"SpotUserDataStream"},
        ),
        ("state = TradingSessionState()\n", {"TradingSessionState"}),
        ("rec = pkg.EquityCurveRecorder()\n", {"EquityCurveRecorder"}),
        ("VenueAssembly(venue, shared)\n", {"VenueAssembly"}),
    ],
)
def test_guard_sees_attribute_calls_aliases_and_per_venue_state(
    source: str, expected: set[str]
) -> None:
    """Review F3: the first version matched only a bare `Name(...)` call of
    the ten adapter classes, so these five spellings passed the guard."""
    assert _constructed_venue_adapters(source, "<fixture>") == expected
