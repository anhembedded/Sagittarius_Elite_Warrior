"""Probes for the capability-catalog guard (`EPIC-037A`): the parser and the AST helpers
can fail, each in the way a real mistake would (a misspelled head, a same-named symbol from
another module). The guard that uses them is
`test_every_support_package_is_in_the_catalog.py`.

Retire when: that guard is retired.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.render_capability_index import (
    Capability,
    parse_docstring,
    with_table,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.capability_catalog_checks import (
    PACKAGE,
    defined_names,
    imports_from,
    imports_the_capability,
    owning_unit,
    symbol_sites,
)

_GOOD = """Summary line.

Capability: Choose a pair
    Also: picker, chooser
    Use: Overlay, Source
    User: src/modules/x/ui/y.py
    Status: stable
"""


def test_a_well_formed_block_parses() -> None:
    parsed = parse_docstring("src/support/a.py", _GOOD)
    assert parsed.problems == ()
    (capability,) = parsed.capabilities
    assert capability.symbols == ("Overlay", "Source")
    assert capability.synonyms == ("picker", "chooser")
    assert capability.where == "src/support/a.py"


def test_a_package_marker_is_located_at_its_directory() -> None:
    parsed = parse_docstring("src/support/k/p/__init__.py", _GOOD)
    assert parsed.capabilities[0].where == "src/support/k/p/"


def test_a_continuation_line_extends_the_field_above() -> None:
    text = _GOOD.replace("Use: Overlay, Source", "Use: Overlay,\n        Source")
    assert parse_docstring("a.py", text).capabilities[0].symbols == (
        "Overlay",
        "Source",
    )


def test_two_blocks_in_one_docstring_are_two_rows() -> None:
    parsed = parse_docstring("a.py", _GOOD + "\n" + _GOOD.replace("pair", "range"))
    assert len(parsed.capabilities) == 2


def test_a_missing_required_field_is_a_problem() -> None:
    text = _GOOD.replace("    User: src/modules/x/ui/y.py\n", "")
    parsed = parse_docstring("a.py", text)
    assert parsed.capabilities == ()
    assert any("missing field `User:`" in p for p in parsed.problems)


def test_a_misspelled_head_is_a_problem_not_a_skipped_row() -> None:
    for head in ("Capabilty: x", "capability: x", "Capabilities: x"):
        parsed = parse_docstring("a.py", head)
        assert parsed.capabilities == ()
        assert parsed.problems, head


def test_an_unknown_field_is_a_problem() -> None:
    text = _GOOD.replace("    Also:", "    Alias:")
    assert any("Alias" in p for p in parse_docstring("a.py", text).problems)


def test_the_status_grammar_is_enforced() -> None:
    assert parse_docstring("a.py", _GOOD.replace("stable", "fine")).problems
    deprecated = parse_docstring("a.py", _GOOD.replace("stable", "deprecated -> Other"))
    assert deprecated.problems == ()
    assert deprecated.capabilities[0].replacement == "Other"


def test_a_user_must_be_a_source_path() -> None:
    text = _GOOD.replace("src/modules/x/ui/y.py", "somewhere")
    assert parse_docstring("a.py", text).problems


def test_a_mention_in_a_string_is_not_an_import() -> None:
    assert imports_from('x = "SymbolPickerOverlay"\n') == set()
    assert imports_from("from pkg.mod import Name as Other\n") == {("pkg.mod", "Name")}
    assert imports_from("from . import Name\n") == set()


def _capability(source: str) -> Capability:
    (capability,) = parse_docstring(source, _GOOD).capabilities
    return capability


def test_a_same_named_symbol_from_another_module_is_not_a_user() -> None:
    capability = _capability("src/support/k/overlay.py")  # declares Overlay, Source
    mod = f"{PACKAGE}.src.support.k.overlay"
    assert imports_the_capability(f"from {mod} import Overlay\n", capability)
    assert imports_the_capability(
        f"from {PACKAGE}.src.support.k import Overlay\n", capability
    )
    assert not imports_the_capability("from other.place import Overlay\n", capability)
    assert not imports_the_capability(f"from {mod} import Unrelated\n", capability)
    assert not imports_the_capability(
        f"from {PACKAGE}.src.support.kk import Overlay\n", capability
    )


def test_defined_names_see_classes_functions_imports_and_aliases() -> None:
    source = "from p import R\nclass C: ...\ndef f(): ...\nV = 1\ntype T = int\n"
    assert defined_names(source) == {"R", "C", "f", "V", "T"}
    assert defined_names("def f():\n    class Inner: ...\n") == {"f"}


def test_a_package_marker_may_use_symbols_defined_beside_it(tmp_path: Path) -> None:
    package = tmp_path / "src" / "support" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""doc"""\n', encoding="utf-8")
    (package / "mod.py").write_text("class Overlay: ...\n", encoding="utf-8")
    capability = parse_docstring("src/support/pkg/__init__.py", _GOOD).capabilities[0]
    sites = symbol_sites(tmp_path, capability)
    assert package / "mod.py" in sites
    assert symbol_sites(
        tmp_path, parse_docstring("src/support/a.py", _GOOD).capabilities[0]
    ) == [tmp_path / "src/support/a.py"]
    package_import = f"from {PACKAGE}.src.support.pkg.mod import Overlay\n"
    assert imports_the_capability(package_import, capability)


def test_a_file_belongs_to_its_nearest_unit() -> None:
    root = Path("/r/src/support")
    units = {root / "ui_kit", root / "ui_kit" / "state"}
    nested = root / "ui_kit" / "state" / "adapters" / "s.py"
    assert owning_unit(nested, units) == root / "ui_kit" / "state"
    assert owning_unit(root / "ui_kit" / "x.py", units) == root / "ui_kit"
    assert owning_unit(root / "other" / "x.py", units) is None


def test_with_table_replaces_only_the_block() -> None:
    text = "head\n<!-- capabilities:begin -->\nold\n<!-- capabilities:end -->\ntail\n"
    assert with_table(text, "NEW") == (
        "head\n<!-- capabilities:begin -->\nNEW\n<!-- capabilities:end -->\ntail\n"
    )
