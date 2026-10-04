"""`EPIC-031B` — the engine and every dependency CI installs are pinned.

Before this, CI cloned the engine's `main` and installed loose requirements,
so two runs of one commit could build different code. `engine.ref` names one
engine commit; `requirements.lock` (`uv pip compile --universal`) names every
transitive version. This test keeps the three files agreeing.

Retire when: the engine is published as a versioned package that
`requirements.txt` pins like any other dependency.
"""

from __future__ import annotations

import re

from Sagittarius_Elite_Warrior.src.core.repo_root import repo_root

_ROOT = repo_root()
_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _normalised(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def test_the_engine_is_pinned_to_one_commit() -> None:
    ref = (_ROOT / "engine.ref").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9a-f]{40}", ref), (
        f"engine.ref must hold a full commit sha, not {ref!r}"
    )


def test_every_requirement_is_pinned_in_the_lock() -> None:
    requirements = {
        _normalised(match.group(1))
        for line in (_ROOT / "requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if (match := _NAME.match(line.strip()))
    }
    locked = {
        _normalised(line.split("==", 1)[0])
        for line in (_ROOT / "requirements.lock")
        .read_text(encoding="utf-8")
        .splitlines()
        if "==" in line and not line.startswith((" ", "#"))
    }
    assert requirements, "requirements.txt names no dependency"
    assert requirements <= locked, (
        f"not in requirements.lock: {sorted(requirements - locked)}; re-run "
        "`uv pip compile requirements.txt --universal --python-version 3.12 -o requirements.lock`"
    )


def test_ci_installs_the_lock_and_the_pinned_engine() -> None:
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements.lock" in workflow
    assert "engine.ref" in workflow
    assert "git clone --depth 1" not in workflow, (
        "CI must not clone the engine's moving main"
    )
