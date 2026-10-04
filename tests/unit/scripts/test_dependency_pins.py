"""`EPIC-031B` — the engine and every dependency CI installs are pinned.

Before this, CI cloned the engine's `main` and installed loose requirements,
so two runs of one commit could build different code. `engine.ref` names one
engine commit; `requirements.lock` (`uv pip compile --universal`) names every
transitive version. This test keeps the three files agreeing.

`BUG-147`: CI installed `engine.ref`'s commit, but `run-ui.ps1` installed the
engine's moving `main`, `run.ps1` installed none, the app's reinstall hint
named `main` too, and `ci-local.ps1`'s mypy step put a sibling engine checkout
on `MYPYPATH`, ahead of the installed engine. So a machine could run, and
type-check against, an engine CI never built. Every install now goes through
`scripts/engine_pin.py`, and the gate checks the engine it uses is the pinned one.

Retire when: the engine is published as a versioned package that
`requirements.txt` pins like any other dependency.
"""

from __future__ import annotations

import re

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import repo_root

_ROOT = repo_root()
_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
_ENGINE_URL = "github.com/anhembedded/Sagittarius_Engine.git"
_INSTALLER = "scripts/engine_pin.py"
_INSTALL = re.compile(r"engine_pin\.py\W{0,3}install")
_CHECK = re.compile(r"engine_pin\.py\W{0,3}check")


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
    assert _INSTALL.search(workflow), f"CI must install the engine with {_INSTALLER}"
    assert "git clone --depth 1" not in workflow, (
        "CI must not clone the engine's moving main"
    )


def _engine_url_holders() -> list[str]:
    scanned = [
        *(_ROOT / "scripts").glob("*.ps1"),
        *(_ROOT / "scripts").glob("*.py"),
        *(_ROOT / "src").rglob("*.py"),
        *(_ROOT / ".github" / "workflows").glob("*.yml"),
        _ROOT / "README.md",
    ]
    return sorted(
        path.relative_to(_ROOT).as_posix()
        for path in scanned
        if _ENGINE_URL in path.read_text(encoding="utf-8")
    )


def test_only_the_installer_names_where_the_engine_comes_from() -> None:
    """`BUG-147` — a second place that installs the engine is a second engine."""
    assert _engine_url_holders() == [_INSTALLER]


@pytest.mark.parametrize("launcher", ["scripts/run-ui.ps1", "scripts/run.ps1"])
def test_every_launcher_installs_the_pinned_engine(launcher: str) -> None:
    text = (_ROOT / launcher).read_text(encoding="utf-8")
    assert _INSTALL.search(text), (
        f"{launcher} must install the engine with {_INSTALLER}"
    )


def test_the_gate_checks_the_pin_and_puts_no_engine_checkout_on_a_path() -> None:
    """`BUG-147` — mypy read a sibling engine checkout named on `MYPYPATH`."""
    gate = (_ROOT / "scripts" / "ci-local.ps1").read_text(encoding="utf-8")
    assert _CHECK.search(gate), f"ci-local.ps1 must run {_INSTALLER} check"
    assert "Sagittarius_Engine" not in gate
