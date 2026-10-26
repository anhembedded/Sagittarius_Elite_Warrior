"""Guard: every type the remote link carries has its round-trip contract test (`EPIC-047A`).

**Why this exists.** The link's closed list (`src/shell/wire_roots.py`) is the only place a
type becomes carriable, and a wire form nobody round-tripped is a wrong number on a
real-money screen waiting for its first message. A root is added in one entry; this guard
makes the second step, its contract test, impossible to forget.

**What it enforces.** Each registered root name appears as `ROOT = "<name>"` in exactly one
`tests/unit/support/wire/contract/test_root_*.py`, and that file calls `assert_round_trips`;
a contract test whose root is not registered (a retired root) fails too.

Retire when: the contract test per root is generated from the registry itself, which needs a
way to build a full instance of a type the codec can already read; then this guard is the
generator's own completeness check.
"""

from __future__ import annotations

import re
from pathlib import Path

from Sagittarius_Elite_Warrior.src.shell.wire_roots import link_roots

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONTRACT_DIR = _REPO_ROOT / "tests" / "unit" / "support" / "wire" / "contract"
_ROOT_LINE = re.compile(r'^ROOT = "(sew\.[a-z0-9-]+/[0-9]+)"$', re.MULTILINE)


def _declared() -> dict[str, list[str]]:
    declared: dict[str, list[str]] = {}
    for path in sorted(_CONTRACT_DIR.glob("test_root_*.py")):
        text = path.read_text(encoding="utf-8")
        match = _ROOT_LINE.search(text)
        assert match, f'{path.name} declares no ROOT = "sew.…/1"'
        assert "assert_round_trips(" in text, (
            f"{path.name} never calls assert_round_trips"
        )
        declared.setdefault(match.group(1), []).append(path.name)
    return declared


def test_every_registered_root_has_exactly_one_contract_test() -> None:
    declared = _declared()
    missing = sorted(set(link_roots().names) - declared.keys())
    assert not missing, (
        f"roots without a contract test in {_CONTRACT_DIR.name}/: {missing}"
    )
    twice = {name: files for name, files in declared.items() if len(files) > 1}
    assert not twice, f"a root has two contract tests: {twice}"


def test_a_contract_test_names_a_registered_root() -> None:
    unknown = sorted(set(_declared()) - set(link_roots().names))
    assert not unknown, (
        f"contract tests for roots the registry does not list: {unknown}"
    )
