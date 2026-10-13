"""Reading the generated unit file, shared by the service-file tests (`EPIC-038H`)."""

from __future__ import annotations

import shutil
from collections import defaultdict

from Sagittarius_Elite_Warrior.scripts.render_service_files import UNIT_FILE

PWSH = shutil.which("pwsh")
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
