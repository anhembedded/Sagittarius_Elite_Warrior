"""Write, or check, the catalogue of log-call templates the `logs` viewer matches lines against.

`PRO-019` option C: the viewer knows which words of a plain line a log call substituted
because the call sites are read here, with `ast`, into `src/support/log_view/template_catalogue.json`.
`tests/unit/support/log_view/test_the_log_template_catalogue_is_current.py` fails when that file differs
from this output, so a new log call cannot reach the viewer unknown.

Usage:
    python3 scripts/render_log_templates.py           # exit 1 and say so when the file is stale
    python3 scripts/render_log_templates.py --write   # rewrite the file
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Sagittarius_Elite_Warrior.src.support.log_view.template_catalogue_file import (
    CATALOGUE_PATH,
    catalogue_text,
)
from Sagittarius_Elite_Warrior.src.support.log_view.template_extractor import (
    extract_catalogue,
)

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"


def render() -> str:
    return catalogue_text(extract_catalogue(SOURCE_ROOT))


def main(argv: list[str]) -> int:
    text = render()
    if "--write" in argv:
        CATALOGUE_PATH.write_text(text, encoding="utf-8")
        return 0
    current = (
        CATALOGUE_PATH.read_text(encoding="utf-8") if CATALOGUE_PATH.exists() else ""
    )
    if current != text:
        sys.stderr.write(
            "template_catalogue.json is stale: run python3 scripts/render_log_templates.py --write\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
