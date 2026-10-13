"""Every concrete `ISecretStore` under `src/` runs through the shared contract suite.

@details `EPIC-038E` added stores behind one port and a suite that holds each to what
the port promises. A store added later and left out of that suite is held to nothing,
and nothing would say so: this guard reads the classes declared in `src/` and fails
on one the suite does not run. Doubles under `tests/` are not scanned: they are what
the suite is for, not stores the app ships.

Retire when: the port has one implementation again, or the suite enumerates `src/`
itself.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.mainnet.test_secret_store_contract import (
    covered_store_classes,
)

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
_STORE_PORTS = {"ISecretStore", "ISourcedSecretStore"}
_INTERFACE_NAME = re.compile(r"^I[A-Z]")


def _concrete_stores_in_src() -> set[str]:
    found: set[str] = set()
    for path in _SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not _INTERFACE_NAME.match(node.name):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                if bases & _STORE_PORTS:
                    found.add(node.name)
    return found


def test_the_scan_sees_the_stores_it_is_meant_to_guard() -> None:
    assert {"KeyringSecretStore", "SystemdCredentialStore"} <= _concrete_stores_in_src()


def test_every_concrete_secret_store_in_src_is_run_by_the_contract_suite(
    tmp_path: Path,
) -> None:
    missing = _concrete_stores_in_src() - covered_store_classes(tmp_path)

    assert not missing, (
        f"{sorted(missing)} implement ISecretStore but are not in `_BACKENDS` of "
        "test_secret_store_contract.py: add them so the port's promises hold for them"
    )
