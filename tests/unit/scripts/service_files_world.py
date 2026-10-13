"""Reading the generated unit file, shared by the service-file tests (`EPIC-038H`)."""

from __future__ import annotations

import os
import shutil
from collections import defaultdict

import pytest
from Sagittarius_Elite_Warrior.scripts.render_service_files import UNIT_FILE

FORBIDDEN_IN_A_SERVICE = ("log.file", "--dev", "--debug")


def sections(text: str) -> dict[str, dict[str, list[str]]]:
    """A unit file as `{section: {key: [values in order]}}`; a key may repeat."""
    parsed: dict[str, dict[str, list[str]]] = {}
    section: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section = parsed.setdefault(line.strip("[]"), defaultdict(list))
            continue
        key, _, value = line.partition("=")
        section[key].append(value)
    return parsed


def service() -> dict[str, list[str]]:
    return sections(UNIT_FILE.read_text(encoding="utf-8"))["Service"]


def one(values: dict[str, list[str]], key: str) -> str:
    assert len(values[key]) == 1, f"{key} must appear exactly once: {values[key]}"
    return values[key][0]


def require_tool(name: str) -> str:
    """The path of an external tool a test needs, or a skip with a reason on a developer's machine.

    On the GitHub Actions runner the tool must be there: a test that silently skipped
    there would leave the unit and the install script unchecked while the gate stayed
    green, so a missing tool fails the test instead (`EPIC-038H`, review of PR #478).
    """
    path = shutil.which(name)
    if path is not None:
        return path
    if os.environ.get("GITHUB_ACTIONS") == "true":
        pytest.fail(f"{name} is required on CI and is not on PATH")
    pytest.skip(f"{name} is not installed")
