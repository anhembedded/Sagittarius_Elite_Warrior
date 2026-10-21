"""The catalogue as a committed file: one template per line, so a diff reads.

Format (`sew.log-templates/1`): a header object, then one JSON array per template,
`[kinds, piece0, piece1, ...]`, where `kinds` is the string of hole kinds in order.

The header holds the schema and nothing that changes with the templates. It used to carry their
count and two statistics; every pull request that added a log call changed that line, so any two of
them conflicted on it (`BOT-230`). The statistics are computed from the source where they are
checked (`test_the_log_template_catalogue_is_current.py`), not read back from this file.
"""

from __future__ import annotations

import json
from pathlib import Path

from Sagittarius_Elite_Warrior.src.support.log_view.template_extractor import (
    Catalogue,
)
from Sagittarius_Elite_Warrior.src.support.log_view.template_model import LogTemplate

CATALOGUE_PATH = Path(__file__).with_name("template_catalogue.json")
_SCHEMA = "sew.log-templates/1"


def catalogue_text(catalogue: Catalogue) -> str:
    """The exact text of the committed file for `catalogue`."""
    header = {"schema": _SCHEMA}
    lines = ["[", json.dumps(header, ensure_ascii=False) + ","]
    rows = [
        json.dumps(["".join(t.kinds), *t.pieces], ensure_ascii=False)
        for t in catalogue.templates
    ]
    lines.append(",\n".join(rows))
    lines.append("]")
    return "\n".join(lines) + "\n"


def parse_catalogue_text(text: str) -> tuple[LogTemplate, ...]:
    """The templates a file holds; raises `ValueError` when it is not a catalogue.

    The file holds nothing else: the statistics are computed from the source where they are
    checked, so none is invented here. A file written before `BOT-230` still carries them in its
    header; they are ignored."""
    rows = json.loads(text)
    header = rows[0]
    if header.get("schema") != _SCHEMA:
        raise ValueError(f"not a {_SCHEMA} file")
    return tuple(LogTemplate(tuple(row[1:]), tuple(row[0])) for row in rows[1:])


def load_templates(path: Path = CATALOGUE_PATH) -> tuple[LogTemplate, ...]:
    """The shipped templates, or none when the file is missing or unreadable.

    A viewer without its catalogue still works: every line is then read by the
    heuristic."""
    try:
        return parse_catalogue_text(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return ()
