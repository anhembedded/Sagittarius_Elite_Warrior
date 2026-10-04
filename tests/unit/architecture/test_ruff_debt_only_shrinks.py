"""Five ruff rules the tree cannot meet yet only ever lose violations (`EPIC-032C`).

**Why this guard exists.** `code/quality.md` §1, §2 and §7 ask for no `Any` at a
seam, no function-local import and small functions, and `commit-rule.md` §3
forbids `print()` debugging. The 2026-10-04 audit measured 212 `ANN401`, 358
`PLC0415`, 34 `C901` and 247 `T20` hits, too many to fix in one change and too
many to enable as rules. `PLR0904` (over 20 public methods on a class) is a
ruff preview rule with 10 hits, so selecting it in `pyproject.toml` did nothing
(PR #330 review). Unenforced, each count could only grow.

**The ratchet** is `baseline_ruff_debt.json`: per rule, per file, the number of
hits found. A file over its count fails, and so does a new file with any hit; a
file under its count fails until its line is lowered or deleted, so the
baseline never keeps room a fix has freed. It only shrinks.

**Scope** follows the rule each code serves: `quality.md` loads for `src/` and
`scripts/`, so `ANN401`, `PLC0415`, `C901` and `PLR0904` scan the code trees (`src`,
`scripts`, `tools`); `commit-rule.md` §3 holds everywhere, so `T20` also scans
`tests`. A lazy import that `test_module_contribution_laziness.py` requires is
one of the counted `PLC0415` hits, by design. Hits are counted with
`--ignore-noqa`, so a suppression comment cannot hide a new one.

Retire when: a rule's baseline is empty; then it moves to `extend-select` in
`pyproject.toml` (`PLR0904` once it leaves preview) and its key leaves the baseline. The guard goes with the last key.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_FILE = Path(__file__).with_name("baseline_ruff_debt.json")

_CODE_TREES = ("src", "scripts", "tools")
#: rule code -> the trees it is counted in.
RATCHETED_RULES: dict[str, tuple[str, ...]] = {
    "ANN401": _CODE_TREES,
    "C901": _CODE_TREES,
    "PLC0415": _CODE_TREES,
    "PLR0904": _CODE_TREES,
    "T20": (*_CODE_TREES, "tests"),
}

#: Per rule, per file: how many hits.
Debt = dict[str, dict[str, int]]


def ratchet_problems(baseline: Debt, current: Debt) -> list[str]:
    """Every file whose count grew past, or fell below, its baseline line."""
    problems: list[str] = []
    for rule in sorted(set(baseline) | set(current)):
        recorded, found = baseline.get(rule, {}), current.get(rule, {})
        for path in sorted(set(recorded) | set(found)):
            was, now = recorded.get(path, 0), found.get(path, 0)
            if now > was:
                problems.append(
                    f"{rule} {path}: {now} hits, baseline {was} — fix the new ones"
                )
            elif now < was:
                problems.append(
                    f"{rule} {path}: {now} hits, baseline {was} — lower the "
                    "baseline to match"
                )
    return problems


def _rule_of(code: str) -> str | None:
    return next((rule for rule in RATCHETED_RULES if code.startswith(rule)), None)


def measure(root: Path = _REPO_ROOT) -> Debt:
    """Run ruff for the ratcheted rules and count hits per rule and file."""
    trees = sorted({tree for trees in RATCHETED_RULES.values() for tree in trees})
    for tree in trees:
        if not (root / tree).is_dir():
            raise FileNotFoundError(
                f"{root / tree} does not exist; retarget this guard"
            )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            *trees,
            "--select",
            ",".join(RATCHETED_RULES),
            "--output-format",
            "json",
            "--exit-zero",
            "--no-cache",
            # A coded suppression comment must not hide a new hit.
            "--ignore-noqa",
            # PLR0904 is a preview rule; the other four count the same
            # with and without it (measured 2026-10-04).
            "--preview",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    counts: dict[str, Counter[str]] = {rule: Counter() for rule in RATCHETED_RULES}
    for hit in json.loads(completed.stdout):
        rule = _rule_of(hit["code"] or "")
        path = Path(hit["filename"]).resolve().relative_to(root).as_posix()
        if rule is not None and path.split("/", 1)[0] in RATCHETED_RULES[rule]:
            counts[rule][path] += 1
    return {rule: dict(sorted(found.items())) for rule, found in counts.items()}


def ruff_warnings(root: Path = _REPO_ROOT) -> list[str]:
    """Every warning ruff prints on stderr for `root`, under its config.

    Ruff reports some defects only as a warning and still exits clean: a
    preview rule in `extend-select` that never runs (PR #330 review:
    `PLR0904`), or a malformed `noqa` it ignores. This is ruff's counterpart
    of mypy's `warn_unused_configs`.
    """
    completed = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--exit-zero", "."],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        line for line in completed.stderr.splitlines() if line.startswith("warning:")
    ]


def _read_baseline() -> Debt:
    data: Debt = json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))["debt"]
    return data


def test_the_baseline_names_every_ratcheted_rule() -> None:
    assert set(_read_baseline()) == set(RATCHETED_RULES)


def test_the_scan_has_a_subject() -> None:
    """A ruff run that reports nothing lost its subject: the debt is real."""
    current = measure()
    assert all(current[rule] for rule in RATCHETED_RULES), current


def test_ruff_debt_only_shrinks() -> None:
    problems = ratchet_problems(_read_baseline(), measure())
    assert not problems, "\n".join(problems)


def test_a_new_hit_fails() -> None:
    problems = ratchet_problems({"T20": {}}, {"T20": {"src/x.py": 1}})
    assert problems == ["T20 src/x.py: 1 hits, baseline 0 — fix the new ones"]


def test_a_fixed_hit_must_lower_the_baseline() -> None:
    problems = ratchet_problems({"C901": {"src/x.py": 2}}, {"C901": {"src/x.py": 1}})
    assert problems == [
        "C901 src/x.py: 1 hits, baseline 2 — lower the baseline to match"
    ]


def test_a_matching_count_passes() -> None:
    debt = {"ANN401": {"src/x.py": 3}}
    assert ratchet_problems(debt, debt) == []


def test_a_planted_print_is_counted(tmp_path: Path) -> None:
    for tree in ("src", "scripts", "tools", "tests"):
        (tmp_path / tree).mkdir()
    (tmp_path / "src" / "probe.py").write_text('print("x")\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert measure(tmp_path)["T20"] == {"src/probe.py": 1}


def test_a_noqa_does_not_hide_a_hit(tmp_path: Path) -> None:
    """PR #330 review: a coded `# noqa` silenced the hit from the ratchet."""
    for tree in ("src", "scripts", "tools", "tests"):
        (tmp_path / tree).mkdir()
    (tmp_path / "src" / "probe.py").write_text(
        'print("x")  # noqa: T201\n', encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert measure(tmp_path)["T20"] == {"src/probe.py": 1}


def test_ruff_prints_no_warning() -> None:
    warnings = ruff_warnings()
    assert not warnings, "ruff warnings on the tree:\n" + "\n".join(warnings)


def test_a_selected_preview_rule_is_reported(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ruff.lint]\nextend-select = ["PLR0904"]\n', encoding="utf-8"
    )
    (tmp_path / "probe.py").write_text("x = 1\n", encoding="utf-8")
    assert any("PLR0904" in line for line in ruff_warnings(tmp_path))


def test_a_malformed_noqa_is_reported(tmp_path: Path) -> None:
    """PR #330 review round 2: a comment quoting a noqa read as a broken one."""
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "probe.py").write_text(
        "x = 1  # a `# noqa: T201` here\n", encoding="utf-8"
    )
    assert any("noqa" in line for line in ruff_warnings(tmp_path))
