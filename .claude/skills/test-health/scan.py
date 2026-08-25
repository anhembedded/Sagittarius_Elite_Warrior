#!/usr/bin/env python3
"""
Mechanical test-integrity scanner for the `test-health` skill.

Answers one question only: *are the tests themselves trustworthy?* — not
"do they pass" (that is `scripts/ci-local.ps1`'s job, and it needs Windows +
PySide6 + the engine installed, which this scanner deliberately does not).

Every check here is a fact, not a judgement: it reports what is in the tree
and lets the caller decide what it means. Stdlib only, no third-party import,
so it runs anywhere Python 3.11 runs — including a headless agent session with
none of the app's dependencies installed.

Usage:
    python3 .claude/skills/test-health/scan.py            # human summary
    python3 .claude/skills/test-health/scan.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
TESTS = REPO / "tests"

#: `tests/integration/presentation/ui` is reported as its own tier: it is
#: the only directory the project excludes from default CI, so folding it
#: into `integration` would hide exactly the number worth watching.
_UI_TIER_DEPTH = 2
#: Findings lists are printed in full; asset lists are not — 22 orphaned
#: QML files is a count, not 22 things to read every three days.
_ASSET_PREVIEW = 5

#: Names that count as "this test actually checked something". A bare
#: `assert` is the common case; the rest are the codebase's own idioms for
#: asserting without the keyword (Qt signal waits genuinely fail the test on
#: timeout, so they are real assertions).
_ASSERTING_CALLS = {
    "raises",
    "fail",
    "waitSignal",
    "waitUntil",
    "waitExposed",
    "approx",
    "assert_frame_equal",
}

#: Docstrings making one of these promises are checked against what the body
#: actually asserts (check C3). Deliberately narrow — a promise of *silence*
#: ("no errors", "cleanly") is the class that rots invisibly, because the
#: obvious weak assertion (`is not None`) looks like it covers it.
_SILENCE_PROMISES = re.compile(
    r"\b(zero|no)\s+\w*\s*(qml\s+)?(error|warning|exception)s?\b"
    r"|\bcleanly\b|\bclean\b|\brenders?\s+clean",
    re.IGNORECASE,
)
_SILENCE_EVIDENCE = re.compile(
    r"error|warning|exception|stderr|caplog|record|message|silent", re.IGNORECASE
)

#: A module-level constant used to drive `@pytest.mark.parametrize` is an
#: allowlist: it can only catch removal of something a human remembered to
#: list. One of these constructs in the same file means the file also proves
#: the list is complete against a live scan (check C6).
_SCAN_MARKERS = {
    "__subclasses__",
    "iterdir",
    "glob",
    "rglob",
    "walk",
    "walk_packages",
    "iter_modules",
    "discover_previews",
    "get_type_hints",
}


def _iter_test_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if path.name == "conftest.py" or path.name.startswith("test_"):
            yield path


def _tier_of(path: Path) -> str:
    rel = path.relative_to(TESTS).parts
    if not rel:
        return "?"
    if (
        rel[0] == "integration"
        and len(rel) > _UI_TIER_DEPTH
        and rel[1:3] == ("presentation", "ui")
    ):
        return "integration/presentation/ui"
    return rel[0]


def _decorator_names(node: ast.AST) -> set[str]:
    found: set[str] = set()
    for dec in getattr(node, "decorator_list", []):
        for sub in ast.walk(dec):
            if isinstance(sub, ast.Name):
                found.add(sub.id)
            elif isinstance(sub, ast.Attribute):
                found.add(sub.attr)
    return found


def _has_assertion(fn: ast.FunctionDef) -> bool:
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Assert):
            return True
        if isinstance(sub, ast.Call):
            name = None
            if isinstance(sub.func, ast.Attribute):
                name = sub.func.attr
            elif isinstance(sub.func, ast.Name):
                name = sub.func.id
            if name and (
                name in _ASSERTING_CALLS
                or name.startswith("assert_")
                or name.startswith("_assert")
            ):
                return True
    return False


def _asserts_of(fn: ast.FunctionDef) -> list[ast.Assert]:
    return [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]


def _locally_constructed(fn: ast.FunctionDef) -> set[str]:
    """Names assigned from a *class construction* inside this function.

    Deliberately not "any call": `handler = container.resolve(Cmd)` genuinely
    can return None when the binding is missing — that is the whole point of
    the DI sanity tests — whereas `window = MainWindow(app)` cannot. Only the
    latter makes `assert x is not None` unable to fail, so only CapWords
    callees count here.
    """
    built: set[str] = set()
    for sub in ast.walk(fn):
        if not (isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call)):
            continue
        func = sub.value.func
        callee = func.id if isinstance(func, ast.Name) else None
        if callee is None or not callee[:1].isupper():
            continue
        for tgt in sub.targets:
            if isinstance(tgt, ast.Name):
                built.add(tgt.id)
    return built


def _is_vacuous(test: ast.expr, built: set[str]) -> str | None:
    """Returns a reason string when this assertion cannot meaningfully fail."""
    if isinstance(test, ast.Constant) and test.value:
        return f"assert {test.value!r} — constant truthy"
    if (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
        and isinstance(test.left, ast.Name)
        and test.left.id in built
    ):
        return (
            f"assert {test.left.id} is not None — {test.left.id} was constructed "
            f"in this test; a constructor returning None is not a reachable state"
        )
    if (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.GtE)
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == 0
        and isinstance(test.left, ast.Call)
        and isinstance(test.left.func, ast.Name)
        and test.left.func.id == "len"
    ):
        return "assert len(...) >= 0 — always true"
    return None


def _live_string_constants(py: Path) -> set[str]:
    """String literals a module actually evaluates — docstrings excluded.

    Comments never reach the AST at all; docstrings do, and they are exactly
    where a migrated-away asset keeps getting mentioned ("kept on disk,
    unloaded"). Counting a docstring mention as a live reference would make
    check C8 permanently blind to the case it exists for.
    """
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))

    return {
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and id(n) not in docstrings
    }


def _scan_orphaned_assets() -> list[dict[str, Any]]:
    """Non-Python assets under src/ that only the tests still reach for.

    A guard test outliving the thing it guards is worse than no test: it keeps
    reporting green about an artifact production stopped loading, and it costs
    CI time to say nothing.
    """
    src = REPO / "src"
    if not src.is_dir():
        return []

    assets = [
        f
        for f in src.rglob("*")
        if f.is_file()
        and f.suffix.lower() in {".qml", ".ui", ".qrc"}
        and "__pycache__" not in f.parts
    ]
    if not assets:
        return []

    src_strings: set[str] = set()
    for py in src.rglob("*.py"):
        src_strings |= _live_string_constants(py)
    src_blob = "\n".join(src_strings)

    test_blob = "\n".join(
        py.read_text(encoding="utf-8", errors="ignore") for py in TESTS.rglob("*.py")
    )

    orphaned: list[dict[str, Any]] = []
    for asset in assets:
        name = asset.name
        if name in src_blob:
            continue
        guarded = name in test_blob
        orphaned.append(
            {
                "file": str(asset.relative_to(REPO)),
                "guarded_by_tests": guarded,
            }
        )
    return orphaned


def _scan_contract() -> list[dict[str, Any]]:
    """Which clauses of the project's own test rules are actually enforced.

    A rule nobody executes is not a rule. `contract.json` restates each
    mandatory clause as something greppable; a clause with zero evidence in
    the tier it governs is a written promise the suite never kept.
    """
    config = Path(__file__).resolve().parent / "contract.json"
    if not config.is_file():
        return []
    clauses = json.loads(config.read_text(encoding="utf-8"))["clauses"]

    results: list[dict[str, Any]] = []
    for clause in clauses:
        target = REPO / clause["evidence_dir"]
        pattern = re.compile(clause["evidence_pattern"])
        hits = [
            f"{py.relative_to(REPO)}:{num}"
            for py in sorted(target.rglob("*.py"))
            if target.is_dir()
            for num, line in enumerate(
                py.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            )
            if pattern.search(line)
        ]
        results.append({**clause, "hits": hits[:5], "hit_count": len(hits)})
    return results


def scan() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    tier_counts: dict[str, int] = defaultdict(int)
    tier_files: dict[str, int] = defaultdict(int)
    fixtures: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    def add(code: str, path: Path, line: int, detail: str) -> None:
        findings.append(
            {
                "check": code,
                "file": str(path.relative_to(REPO)),
                "line": line,
                "detail": detail,
            }
        )

    for path in _iter_test_files(TESTS):
        tier = _tier_of(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # a test file that will not even import
            add("C0", path, exc.lineno or 0, f"SyntaxError: {exc.msg}")
            continue

        if path.name.startswith("test_"):
            tier_files[tier] += 1

        module_consts: dict[str, int] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(
                node.value, (ast.List, ast.Dict, ast.Set, ast.Tuple)
            ):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        module_consts[tgt.id] = node.lineno

        source = path.read_text(encoding="utf-8")
        file_has_scan = any(marker in source for marker in _SCAN_MARKERS)
        parametrized_consts: set[str] = set()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decs = _decorator_names(node)

            if "fixture" in decs:
                fixtures[tier][node.name].append(
                    f"{path.relative_to(REPO)}:{node.lineno}"
                )
                skips = any(
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "skip"
                    for call in ast.walk(node)
                )
                if skips:
                    add(
                        "C4",
                        path,
                        node.lineno,
                        f"fixture `{node.name}` calls pytest.skip — every test "
                        f"depending on it disappears silently and the tier still "
                        f"reports green",
                    )

            if "parametrize" in decs:
                for dec in node.decorator_list:
                    for sub in ast.walk(dec):
                        if isinstance(sub, ast.Name) and sub.id in module_consts:
                            parametrized_consts.add(sub.id)

            if not node.name.startswith("test_"):
                continue
            tier_counts[tier] += 1

            if not _has_assertion(node):  # type: ignore[arg-type]
                add(
                    "C1",
                    path,
                    node.lineno,
                    f"`{node.name}` contains no assertion — it cannot fail",
                )
                continue

            asserts = _asserts_of(node)  # type: ignore[arg-type]
            built = _locally_constructed(node)  # type: ignore[arg-type]
            reasons = [r for a in asserts if (r := _is_vacuous(a.test, built))]
            if reasons and len(reasons) == len(asserts):
                add(
                    "C2",
                    path,
                    node.lineno,
                    f"`{node.name}` — every assertion is vacuous: {reasons[0]}",
                )

            doc = ast.get_docstring(node) or ""
            if _SILENCE_PROMISES.search(doc):
                body_src = ast.get_source_segment(source, node) or ""
                body_only = body_src.replace(doc, "")
                promise = _SILENCE_PROMISES.search(doc)
                if promise and not _SILENCE_EVIDENCE.search(body_only):
                    add(
                        "C3",
                        path,
                        node.lineno,
                        f"`{node.name}` docstring promises "
                        f'"{promise.group(0).strip()}" but the body never '
                        f"inspects errors/warnings/log records",
                    )

        for const in sorted(parametrized_consts):
            if not file_has_scan:
                add(
                    "C6",
                    path,
                    module_consts[const],
                    f"`{const}` drives parametrize but this file never scans the "
                    f"real source of truth — the list catches deletions, never "
                    f"an addition someone forgot to register",
                )

    for tier, by_name in fixtures.items():
        for name, sites in by_name.items():
            if len(sites) > 1:
                first_file, first_line = sites[0].rsplit(":", 1)
                findings.append(
                    {
                        "check": "C7",
                        "file": first_file,
                        "line": int(first_line),
                        "detail": (
                            f"fixture `{name}` is defined {len(sites)}x in "
                            f"`{tier}` ({', '.join(sites)}) — copies drift; "
                            f"there is no single definition to keep correct"
                        ),
                    }
                )

    return {
        "tiers": {
            t: {"tests": tier_counts[t], "files": tier_files[t]}
            for t in sorted(tier_counts)
        },
        "ci_exclusions": _scan_ci_exclusions(),
        "orphaned_assets": _scan_orphaned_assets(),
        "contract": _scan_contract(),
        "findings": sorted(findings, key=lambda f: (f["check"], f["file"], f["line"])),
        "bug_board": _scan_bug_board(),
    }


def _scan_ci_exclusions() -> list[dict[str, Any]]:
    """What the project's own CI entry point refuses to run by default."""
    out: list[dict[str, Any]] = []
    ci = REPO / "scripts" / "ci-local.ps1"
    if not ci.is_file():
        return out
    text = ci.read_text(encoding="utf-8")
    for num, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for match in re.finditer(r'--ignore=([^\s"\']+)', stripped):
            target = match[1]
            key = target.rstrip("/")
            # An --ignore is only a real exclusion when nothing else in the
            # script runs that target on its own. `tests/sanity` is ignored by
            # the parallel run *because* it runs sequentially in a background
            # job — that is scheduling, not exclusion. Prose in the script's
            # help block mentions paths too, so only lines that actually bind
            # the path to a variable or push it onto an argument list count.
            elsewhere = [
                ln
                for ln in text.splitlines()
                if key in ln
                and "--ignore" not in ln
                and re.search(r'(=\s*["\']|\+=)', ln)
            ]
            out.append(
                {
                    "file": "scripts/ci-local.ps1",
                    "line": str(num),
                    "target": target,
                    "run_elsewhere": bool(elsewhere),
                }
            )
    return out


def _scan_bug_board() -> dict[str, int]:
    board = REPO / "Tasks" / "bug_report"
    if not board.is_dir():
        return {}
    return {
        "open": len(list((board / "incomplete").glob("BUG-*.md")))
        if (board / "incomplete").is_dir()
        else 0,
        "closed": len(list((board / "completed").glob("BUG-*.md")))
        if (board / "completed").is_dir()
        else 0,
    }


_CHECK_TITLES = {
    "C0": "Test file does not parse",
    "C1": "Test with no assertion — cannot fail",
    "C2": "Every assertion vacuous — cannot fail meaningfully",
    "C3": "Docstring promises more than the body asserts",
    "C4": "Fixture skips silently — tests vanish, tier stays green",
    "C6": "Parametrize allowlist with no completeness guard",
    "C7": "Fixture duplicated across a tier — drift surface",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    result = scan()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("TIER SHAPE")
    for tier, counts in result["tiers"].items():
        print(f"  {tier:34s} {counts['tests']:5d} tests  {counts['files']:4d} files")

    print("\nEXCLUDED FROM DEFAULT CI")
    real = [e for e in result["ci_exclusions"] if not e["run_elsewhere"]]
    scheduled = [e for e in result["ci_exclusions"] if e["run_elsewhere"]]
    for exc in real:
        tier = exc["target"].rstrip("/").split("tests/", 1)[-1]
        lost = result["tiers"].get(tier, {}).get("tests", "?")
        print(
            f"  NOT RUN     {exc['target']}  ({lost} tests)  "
            f"[{exc['file']}:{exc['line']}]"
        )
    for exc in scheduled:
        print(f"  (separate job) {exc['target']}  [{exc['file']}:{exc['line']}]")
    if not result["ci_exclusions"]:
        print("  (none)")

    print("\nRULE CONTRACT — is each mandatory clause actually enforced?")
    for clause in result["contract"]:
        mark = "ENFORCED" if clause["hit_count"] else "NOT ENFORCED"
        print(
            f"  {mark:13s} {clause['id']}  ({clause['hit_count']} hits in "
            f"{clause['evidence_dir']})"
        )
        print(f"                {clause['source']} — {clause['requirement']}")

    orphans = result["orphaned_assets"]
    if orphans:
        guarded = [o for o in orphans if o["guarded_by_tests"]]
        print(
            f"\nORPHANED ASSETS  {len(orphans)} file(s) under src/ that no "
            f"src/*.py loads"
        )
        print(f"  of which still referenced by tests: {len(guarded)}")
        for orphan in orphans[:_ASSET_PREVIEW]:
            print(
                f"    {orphan['file']}"
                f"{'  [tests still guard this]' if orphan['guarded_by_tests'] else ''}"
            )
        if len(orphans) > _ASSET_PREVIEW:
            print(f"    ... and {len(orphans) - _ASSET_PREVIEW} more")

    print(
        f"\nBUG BOARD  open={result['bug_board'].get('open', 0)}  "
        f"closed={result['bug_board'].get('closed', 0)}"
    )

    by_check: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in result["findings"]:
        by_check[finding["check"]].append(finding)

    print(f"\nINTEGRITY FINDINGS  ({len(result['findings'])} total)")
    for code in sorted(by_check):
        items = by_check[code]
        print(f"\n  [{code}] {_CHECK_TITLES.get(code, code)} — {len(items)}")
        for item in items:
            print(f"    {item['file']}:{item['line']}")
            print(f"      {item['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
