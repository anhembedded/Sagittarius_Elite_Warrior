"""A venue is shown as its title ("Spot Testnet"), never its identifier (`EPIC-034A`).

`TradingVenue.value` (`spot_testnet`) is an identifier: a settings key, an
object name, a command id, a log field. The Bots table, the Plan read-out and
the New bot dialog showed it as text, and the title map existed only in the
Strategies panel. `TradingVenue.display_name` is the one map, in contracts.

What is scanned: UI code (every `ui/` package of a module, `support/ui_kit`,
`support/charting`, `presentation`, `shell`). What is found: `.value` read off a
name or attribute that ends in `venue` (`venue`, `_venue`, `current_venue`),
outside a logging call. A venue held under a name that does not end so is not
seen: the guard reads names, not types. The
exemptions are files, each naming the identifier it needs.

Retire when: the UI never holds a `TradingVenue` (no such plan).
"""

from __future__ import annotations

import ast
from pathlib import Path

from .test_display_values_go_through_the_formatter import is_ui

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_LOGGING_CALLS = frozenset(
    {"trace", "debug", "info", "warning", "error", "exception", "critical", "log"}
)

#: path -> the identifier its `venue.value` is.
EXEMPT: dict[str, str] = {
    "src/modules/trading/ui/trade/trade_commands.py": "a command id",
    "src/modules/trading/ui/trade/venue_choice.py": (
        "the remembered state's key and a log field"
    ),
    "src/modules/trading/ui/desk/desk_screen/desk_view.py": "object names",
    "src/modules/trading/ui/desk/desk_screen/desk_dependencies.py": (
        "an owner id and a programming-error message"
    ),
    "src/modules/trading/ui/desk/desk_screen/desk_presenter.py": (
        "a programming-error message"
    ),
    "src/modules/trading/ui/desk/desk_profile.py": "a programming-error message",
    "src/modules/trading/ui/desk/order_entry/order_entry_presenter.py": (
        "a programming-error message"
    ),
}


def _in_logging_call(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    while node in parents:
        node = parents[node]
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _LOGGING_CALLS
        ):
            return True
    return False


def raw_venue_values(source: str) -> list[str]:
    """Each place in `source` that reads a venue's identifier outside a log."""
    tree = ast.parse(source)
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    found: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and node.attr == "value"):
            continue
        owner = node.value
        name = (
            owner.id
            if isinstance(owner, ast.Name)
            else owner.attr
            if isinstance(owner, ast.Attribute)
            else ""
        )
        if name.lower().endswith("venue") and not _in_logging_call(node, parents):
            found.append(f"line {node.lineno}: {name}.value")
    return found


def _ui_sources() -> list[tuple[str, Path]]:
    if not _SRC_ROOT.is_dir():
        raise FileNotFoundError(f"{_SRC_ROOT} does not exist; retarget this guard")
    return [
        (rel, path)
        for path in sorted(_SRC_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts
        and is_ui(rel := path.relative_to(_REPO_ROOT).as_posix())
    ]


def test_the_scan_has_a_subject() -> None:
    assert len(_ui_sources()) > 100


def test_no_ui_code_shows_a_venue_identifier() -> None:
    found = {
        rel: hits
        for rel, path in _ui_sources()
        if rel not in EXEMPT and (hits := raw_venue_values(path.read_text("utf-8")))
    }
    assert not found, (
        "show venue.display_name (src/support/binance_gateway/contracts/trading_venue.py); "
        "an identifier use is exempted by file in EXEMPT:\n"
        + "\n".join(f"{rel}: {', '.join(hits)}" for rel, hits in sorted(found.items()))
    )


def test_every_exemption_names_a_file_that_still_reads_an_identifier() -> None:
    stale = [
        rel
        for rel in EXEMPT
        if not (_REPO_ROOT / rel).is_file()
        or not raw_venue_values((_REPO_ROOT / rel).read_text("utf-8"))
    ]
    assert not stale, f"drop or retarget these exemptions: {stale}"


def test_a_planted_raw_venue_value_is_seen() -> None:
    source = "box.addItem(venue.value, venue)\nrow.venue.value\n"
    assert len(raw_venue_values(source)) == 2


def test_a_log_line_and_the_title_are_not_a_raw_value() -> None:
    source = "logger.info('x %s', venue.value)\nlabel = venue.display_name\n"
    assert raw_venue_values(source) == []
